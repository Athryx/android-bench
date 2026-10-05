from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
import threading
import time
import tomllib
from typing import TYPE_CHECKING, Any

from cuttle_cli import CuttleClient
from kbench import (
    BenchmarkResult,
    BenchmarkRun,
    Challenge,
    ChallengeInstance,
    ChallengeResult,
    GlobalRunState,
    Score,
    run_challenges,
)
from kexploit_agent import AgentGroup, Limits, summarize_log
from ksandbox import DockerSandboxProvider, MountInfo

from android_bench.challenge import AndroidAppChallenge, KEEP_GOING_PROMPT
from android_bench.grader import format_reprompt
from android_bench.models import (
    AndroidBenchmarkResult,
    AndroidChallengeResult,
    AndroidExploitScore,
    AttemptRecord,
    Capability,
    ChallengeResumeConfig,
    ChallengeScore,
    FloatScore,
    GraderResult,
    ResumeMode,
    TestGraderResult,
    calculate_scores,
)
from android_bench.sandbox import AndroidBenchSandbox
from android_bench.trace import TranscriptParser, extract_final_response

if TYPE_CHECKING:
    from android_bench.config import BenchmarkConfig

logger = logging.getLogger(__name__)


def _copy_agent_context(
    agent: object, history_file: Path, target_transcript: Path
) -> None:
    agent_context = getattr(agent, "context_path", None)
    if agent_context is None and hasattr(agent, "_context_capture"):
        capture_obj = getattr(agent, "_context_capture")
        if capture_obj is not None:
            agent_context = getattr(capture_obj, "path", None)

    context_file: Path | None = None
    if (
        agent_context is not None
        and isinstance(agent_context, (str, Path))
        and Path(agent_context).is_file()
    ):
        context_file = Path(agent_context)
    else:
        try:
            from kexploit_agent.context_capture import capture_path

            candidate = capture_path(history_file)
        except ImportError:
            candidate = history_file.with_suffix(".context.jsonl")

        if candidate.is_file():
            context_file = candidate
        elif history_file.with_suffix(".context.json").is_file():
            context_file = history_file.with_suffix(".context.json")

    if context_file is not None and context_file.is_file():
        if context_file.name.endswith(".context.json"):
            target_context = target_transcript.with_suffix(".context.json")
        else:
            try:
                from kexploit_agent.context_capture import capture_path

                target_context = capture_path(target_transcript)
            except Exception:
                target_context = target_transcript.with_suffix(".context.jsonl")
        shutil.copy2(
            context_file,
            target_context,
        )


def _save_benchmark_progress(
    output_folder: Path,
    challenge_results: dict[str, Any],
    total_start: float,
) -> AndroidBenchmarkResult:
    scores = [
        getattr(result, "score", 0.0)
        for result in challenge_results.values()
        if getattr(result, "score", None) is not None
    ]
    float_scores = [
        float(s.score if hasattr(s, "score") and not isinstance(s, (int, float)) else s)
        for s in scores
    ]
    total_runtime = time.perf_counter() - total_start
    overall = (
        sum(float_scores) / len(float_scores) if float_scores else 0.0
    )
    benchmark_result = AndroidBenchmarkResult(
        score=overall,
        total_runtime=total_runtime,
        results=challenge_results,
    )
    (output_folder / "results.toml").write_text(
        benchmark_result.model_dump_toml()
    )
    return benchmark_result


def _failed_challenge_result(
    output_folder: Path,
    challenge: Challenge,
    error: Exception,
    runtime: float,
) -> AndroidChallengeResult:
    solution = output_folder / challenge.name
    results_file = solution / "results.toml"
    previous: AndroidChallengeResult | None = None
    if results_file.is_file():
        try:
            previous = AndroidChallengeResult.model_validate_toml(
                results_file.read_text(encoding="utf-8")
            )
        except Exception:
            logger.warning("Could not read partial result for '%s'", challenge.name)

    attempts = {attempt.attempt: attempt for attempt in previous.attempts} if previous else {}
    for attempt_file in (solution / "grading").glob("attempt-*.toml"):
        try:
            attempt = AttemptRecord.model_validate_toml(
                attempt_file.read_text(encoding="utf-8")
            )
        except Exception:
            logger.warning("Could not read graded attempt %s", attempt_file)
            continue
        attempts[attempt.attempt] = attempt

    graded_attempts = [attempts[number] for number in sorted(attempts)]
    score, axes = (
        calculate_scores(graded_attempts[-1])
        if graded_attempts
        else (0.0, {})
    )
    result = AndroidChallengeResult(
        challenge=challenge.name,
        package=previous.package if previous else (
            challenge.definition.package if isinstance(challenge, AndroidAppChallenge) else ""
        ),
        status="failed",
        score=FloatScore(score),
        axes=axes,
        runtime=runtime,
        session_id=previous.session_id if previous else None,
        limit_exceeded=previous.limit_exceeded if previous else None,
        error=f"{type(error).__name__}: {error}",
        attempts=graded_attempts,
    )
    solution.mkdir(parents=True, exist_ok=True)
    results_file.write_text(result.model_dump_toml())
    return result


def run_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    logger.info("Challenge '%s': preparing solution", challenge.name)
    challenge_dir = state.solutions_folder / challenge.name
    solution = challenge_dir / "solution"
    solution.mkdir(parents=True, exist_ok=True)
    prepare_solution = getattr(challenge, "prepare_solution", None)
    if callable(prepare_solution):
        prepare_solution(solution)
    solution_mount = MountInfo(
        src_folder=solution,
        name="solution",
        description="folder to place challenge solution",
        writable=True,
    )
    model_config = challenge.model_config
    start_time = time.perf_counter()
    with AndroidBenchSandbox(
        state,
        challenge.tag,
        challenge.cuttlefish_template,
        [solution_mount],
        name=challenge.name,
        internet_enabled=challenge.internet_enabled,
        extra_hosts={model_config.resolved_api_host: model_config.resolved_guest_addr},
        apps_to_install=(
            challenge.definition.apps_to_install
            if isinstance(challenge, AndroidAppChallenge)
            else ()
        ),
    ) as sandbox:
        if sandbox.sandbox is None:
            raise RuntimeError("solver Docker sandbox is not running")
        ch_limits = getattr(challenge, "limits", None)
        agent_limits = ch_limits if isinstance(ch_limits, Limits) else None
        logger.info("Challenge '%s': creating solver agent", challenge.name)
        agent = challenge.harness.create_agent(
            f"{challenge.name}_agent",
            model_config,
            challenge.system_prompt(sandbox.container_adb_host),
            sandbox.sandbox,
            agent_group=state.run_group,
            limits=agent_limits,
        )
        logger.info("Challenge '%s': solver agent ready", challenge.name)
        raw_sid = getattr(agent, "session_id", None)
        session_id: str | None = (
            str(raw_sid) if isinstance(raw_sid, (str, Path)) else None
        )
        init_result = AndroidChallengeResult(
            challenge=challenge.name,
            session_id=session_id,
            status="running",
            score=FloatScore(0.0),
            axes={},
            runtime=0.0,
        )
        (challenge_dir / "results.toml").write_text(init_result.model_dump_toml())

        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (challenge_dir / "results.toml").write_text(p_res.model_dump_toml())

        outcome: Any
        try:
            with state.manage_agent(agent):
                if isinstance(challenge, AndroidAppChallenge):
                    outcome = challenge.run(
                        ChallengeInstance(solution, agent, sandbox),
                        progress_callback=on_progress,
                    )
                else:
                    outcome = challenge.run(ChallengeInstance(solution, agent, sandbox))
        finally:
            history_path = getattr(agent, "history_path", None)
            if isinstance(history_path, (str, Path)):
                history_file = Path(history_path)
                if history_file.is_file():
                    target_transcript = (
                        state.solutions_folder / f"{challenge.name}_transcript.json"
                    )
                    try:
                        if getattr(challenge, "summarize", False) is True:
                            summarize_log(history_file)
                    finally:
                        shutil.copy2(
                            history_file,
                            target_transcript,
                        )
                        if session_id:
                            session_transcript = (
                                state.solutions_folder / f"{session_id}.jsons"
                            )
                            shutil.copy2(history_file, session_transcript)
                        _copy_agent_context(agent, history_file, target_transcript)

    if isinstance(outcome, AndroidChallengeResult):
        result = outcome
        result.runtime = time.perf_counter() - start_time
    else:
        limit_exceeded = getattr(outcome, "limit_exceeded", None)
        score_val = getattr(outcome, "score", 0.0)
        score_float = float(score_val.score if hasattr(score_val, "score") and not isinstance(score_val, (int, float)) else score_val)
        result = AndroidChallengeResult(
            challenge=challenge.name,
            score=FloatScore(score_float),
            axes=getattr(outcome, "axes", {}),
            runtime=time.perf_counter() - start_time,
            limit_exceeded=limit_exceeded,
            session_id=session_id,
            status="completed",
        )
    (challenge_dir / "results.toml").write_text(result.model_dump_toml())
    return result


def _attempt_sort_key(p: Path) -> int:
    stem = p.stem
    parts = stem.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def resume_challenge(
    state: GlobalRunState,
    challenge: Challenge,
    cfg: ChallengeResumeConfig | None = None,
) -> ChallengeResult:
    if cfg is None:
        cfg = ChallengeResumeConfig(challenge=challenge.name, mode=ResumeMode.AUTO, attempts=1)

    challenge_dir = state.solutions_folder / challenge.name
    solution = challenge_dir / "solution"
    results_file = challenge_dir / "results.toml"
    if not results_file.is_file():
        results_file = challenge_dir / "results.json"
    transcript_file = state.solutions_folder / f"{challenge.name}_transcript.json"
    if not transcript_file.is_file():
        transcript_file = state.solutions_folder / f"{challenge.name}_transcript.jsons"

    if cfg.mode == ResumeMode.NONE:
        if results_file.is_file():
            try:
                content = results_file.read_text(encoding="utf-8")
                return AndroidChallengeResult.model_validate(
                    tomllib.loads(content) if results_file.suffix == ".toml" else json.loads(content)
                )
            except Exception:
                pass
        return AndroidChallengeResult(challenge=challenge.name, status="skipped", score=FloatScore(0.0))

    # 1. Check if challenge is already completed (for auto mode)
    if cfg.mode == ResumeMode.AUTO and results_file.is_file():
        try:
            content = results_file.read_text(encoding="utf-8")
            data = tomllib.loads(content) if results_file.suffix == ".toml" else json.loads(content)
            if data.get("status") == "completed" and data.get("score") is not None:
                logger.info("Challenge '%s': already completed; skipping", challenge.name)
                return AndroidChallengeResult.model_validate(data)
            if data.get("score") is not None and isinstance(data.get("score"), dict):
                if data["score"].get("issues_resolved") is not None:
                    logger.info("Challenge '%s': already completed; skipping", challenge.name)
                    return AndroidChallengeResult.model_validate(data)
        except Exception:
            pass

    # Read existing challenge result if available
    previous: AndroidChallengeResult | None = None
    if results_file.is_file():
        try:
            content = results_file.read_text(encoding="utf-8")
            data = tomllib.loads(content) if results_file.suffix == ".toml" else json.loads(content)
            previous = AndroidChallengeResult.model_validate(data)
        except Exception:
            previous = None

    # Check existing graded attempts
    audit_dir = challenge_dir / "grading"
    existing_attempts: list[AttemptRecord] = []
    if audit_dir.is_dir():
        for att_path in sorted(audit_dir.glob("attempt-*.*"), key=_attempt_sort_key):
            if att_path.suffix in (".toml", ".json"):
                try:
                    content = att_path.read_text(encoding="utf-8")
                    if att_path.suffix == ".toml":
                        existing_attempts.append(
                            AttemptRecord.model_validate_toml(content)
                        )
                    else:
                        existing_attempts.append(
                            AttemptRecord.model_validate_json(content)
                        )
                except Exception:
                    pass

    session_id: str | None = previous.session_id if previous else None
    transcript_parser: TranscriptParser | None = None
    if transcript_file.is_file():
        try:
            transcript_parser = TranscriptParser.from_file(transcript_file)
        except Exception:
            transcript_parser = None

    if session_id is None and transcript_parser is not None:
        session_id = transcript_parser.get_session_id()

    num_graded = len(existing_attempts)
    num_agent_runs = transcript_parser.count_agent_runs() if transcript_parser is not None else 0

    # If no session_id is known and solution doesn't exist, run fresh
    if session_id is None and not challenge_dir.is_dir():
        return run_challenge(state, challenge)

    initial_prompt: str | None = None
    initial_response: str | None = None

    if cfg.mode == ResumeMode.REGRADE:
        resp = ""
        if transcript_file.is_file():
            try:
                resp = extract_final_response(transcript_file)
            except Exception:
                resp = ""
        logger.info("Challenge '%s': regrading current solution (mode=regrade)", challenge.name)
        grade_solution = getattr(challenge, "grade_solution", None)
        if not callable(grade_solution):
            raise TypeError(f"Challenge {challenge.name} does not support grade_solution")
        next_attempt_num = len(existing_attempts) + 1
        record = grade_solution((state, solution), resp, attempt=next_attempt_num, persist=True)
        existing_attempts.append(record)

        if previous is None:
            definition = getattr(challenge, "definition", None)
            pkg = getattr(definition, "package", "")
            previous = AndroidChallengeResult(
                challenge=challenge.name,
                package=pkg,
                session_id=session_id,
            )
        previous.append_attempt(record)
        challenge_dir.mkdir(parents=True, exist_ok=True)
        (challenge_dir / "results.toml").write_text(previous.model_dump_toml())

        if cfg.attempts == 0 or record.issues_resolved:
            logger.info(
                "Challenge '%s': regrade finished with %d attempts (score=%.4f)",
                challenge.name,
                len(existing_attempts),
                float(previous.score),
            )
            return previous

        initial_prompt = record.reprompt or format_reprompt(record)

    elif cfg.mode == ResumeMode.LAST_ATTEMPT:
        if existing_attempts:
            last = existing_attempts[-1]
            initial_prompt = last.reprompt or format_reprompt(last)
        else:
            initial_prompt = None

    elif cfg.mode == ResumeMode.KEEP_GOING:
        initial_prompt = KEEP_GOING_PROMPT

    elif cfg.mode == ResumeMode.AUTO:
        if transcript_parser is not None and num_agent_runs > num_graded:
            try:
                initial_response = transcript_parser.get_final_response()
            except Exception:
                initial_response = None
        elif existing_attempts:
            last = existing_attempts[-1]
            if last.issues_resolved:
                logger.info("Challenge '%s': already resolved; skipping", challenge.name)
                if previous is not None:
                    return previous
                if results_file.is_file():
                    return AndroidChallengeResult.model_validate_toml(results_file.read_text(encoding="utf-8"))
            initial_prompt = last.reprompt or format_reprompt(last)
        else:
            initial_prompt = None

    if cfg.attempts == 0:
        if previous is not None:
            return previous
        if results_file.is_file():
            return AndroidChallengeResult.model_validate_toml(results_file.read_text(encoding="utf-8"))
        return AndroidChallengeResult(challenge=challenge.name, status="completed", score=FloatScore(0.0))

    # Try to resume agent using BaseAgent.resume
    resumed_agent = None
    if session_id is not None:
        try:
            from kexploit_agent import BaseAgent

            logger.info(
                "Challenge '%s': restoring solver session %s",
                challenge.name,
                session_id,
            )
            ch_limits = getattr(challenge, "limits", None)
            agent_limits = ch_limits if isinstance(ch_limits, Limits) else None
            resumed_agent = BaseAgent.resume(
                session_id,
                history_dir=state.solutions_folder,
                limits=agent_limits,
                delete_sandbox=False,
            )
        except Exception as exc:
            logger.warning(
                "Could not resume agent session %s for challenge '%s': %s",
                session_id,
                challenge.name,
                exc,
            )
            resumed_agent = None

    if resumed_agent is None:
        logger.info(
            "Challenge '%s': starting fresh run due to unavailable previous session",
            challenge.name,
        )
        return run_challenge(state, challenge)

    solution.mkdir(parents=True, exist_ok=True)
    solution_mount = MountInfo(
        src_folder=solution,
        name="solution",
        description="folder to place challenge solution",
        writable=True,
    )
    model_config = challenge.model_config
    start_time = time.perf_counter()

    existing_sb = resumed_agent.sandbox if resumed_agent is not None else None
    with AndroidBenchSandbox(
        state,
        challenge.tag,
        challenge.cuttlefish_template,
        [solution_mount],
        name=challenge.name,
        internet_enabled=challenge.internet_enabled,
        extra_hosts={model_config.resolved_api_host: model_config.resolved_guest_addr},
        existing_sandbox=existing_sb,
        apps_to_install=(
            challenge.definition.apps_to_install
            if isinstance(challenge, AndroidAppChallenge)
            else ()
        ),
    ) as sandbox:
        logger.info("Challenge '%s': resumed solver agent ready", challenge.name)

        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (challenge_dir / "results.toml").write_text(p_res.model_dump_toml())

        outcome: Any
        try:
            with state.manage_agent(resumed_agent):
                if isinstance(challenge, AndroidAppChallenge):
                    outcome = challenge.run(
                        ChallengeInstance(solution, resumed_agent, sandbox),
                        initial_attempts=existing_attempts,
                        initial_response=initial_response,
                        start_attempt_index=num_graded,
                        additional_attempts=cfg.attempts,
                        initial_prompt=initial_prompt,
                        progress_callback=on_progress,
                    )
                else:
                    outcome = challenge.run(
                        ChallengeInstance(solution, resumed_agent, sandbox)
                    )
        finally:
            history_path = getattr(resumed_agent, "history_path", None)
            if isinstance(history_path, (str, Path)):
                history_file = Path(history_path)
                if history_file.is_file():
                    target_transcript = (
                        state.solutions_folder / f"{challenge.name}_transcript.json"
                    )
                    try:
                        if getattr(challenge, "summarize", False) is True:
                            summarize_log(history_file)
                    finally:
                        raw_resumed_sid = getattr(resumed_agent, "session_id", None)
                        resumed_session_id = (
                            str(raw_resumed_sid)
                            if isinstance(raw_resumed_sid, (str, Path))
                            else None
                        )
                        if resumed_session_id:
                            session_transcript = (
                                state.solutions_folder / f"{resumed_session_id}.jsons"
                            )
                            if history_file.resolve() != session_transcript.resolve():
                                shutil.copy2(history_file, session_transcript)
                        if history_file.resolve() != target_transcript.resolve():
                            shutil.copy2(history_file, target_transcript)
                        _copy_agent_context(resumed_agent, history_file, target_transcript)

    raw_resumed_sid = getattr(resumed_agent, "session_id", None)
    resumed_session_id = (
        str(raw_resumed_sid)
        if isinstance(raw_resumed_sid, (str, Path))
        else None
    )
    if isinstance(outcome, AndroidChallengeResult):
        result = outcome
        result.runtime = time.perf_counter() - start_time
        if resumed_session_id and not result.session_id:
            result.session_id = resumed_session_id
    else:
        raw_limit = getattr(outcome, "limit_exceeded", None)
        limit_exceeded = str(raw_limit) if isinstance(raw_limit, (str, Path)) else None
        score_val = getattr(outcome, "score", 0.0)
        score_float = float(score_val.score if hasattr(score_val, "score") and not isinstance(score_val, (int, float)) else score_val)
        raw_axes = getattr(outcome, "axes", {})
        axes = raw_axes if isinstance(raw_axes, dict) else {}
        result = AndroidChallengeResult(
            challenge=challenge.name,
            score=FloatScore(score_float),
            axes=axes,
            runtime=time.perf_counter() - start_time,
            limit_exceeded=limit_exceeded,
            session_id=resumed_session_id,
            status="completed",
        )
    (challenge_dir / "results.toml").write_text(result.model_dump_toml())
    return result


def run_benchmark(
    run: BenchmarkRun,
    benchmark_config: BenchmarkConfig | None = None,
    *,
    resume: bool = False,
    resume_configs: dict[str, ChallengeResumeConfig] | None = None,
) -> AndroidBenchmarkResult:
    run.output_folder.mkdir(exist_ok=True, parents=True)
    if benchmark_config is not None:
        (run.output_folder / "challenge.toml").write_text(
            benchmark_config.formatted_toml()
        )

    state = GlobalRunState(
        sandbox_provider=DockerSandboxProvider.get(),
        cuttle_client=CuttleClient.from_config(),
        run_group=AgentGroup(run.name),
        grader_group=AgentGroup(f"{run.name} graders"),
        solutions_folder=run.output_folder,
    )
    total_start = time.perf_counter()

    challenge_results: dict[str, ChallengeResult] = {}
    challenges_to_run = list(run.challenges)

    if resume:
        # Load any existing completed results
        results_file = run.output_folder / "results.toml"
        if not results_file.is_file():
            results_file = run.output_folder / "results.json"
        if results_file.is_file():
            try:
                content = results_file.read_text(encoding="utf-8")
                existing_data = tomllib.loads(content) if results_file.suffix == ".toml" else json.loads(content)
                if "results" in existing_data and isinstance(existing_data["results"], dict):
                    for name, res_data in existing_data["results"].items():
                        challenge_results[name] = AndroidChallengeResult.model_validate(res_data)
            except Exception:
                pass

        for ch in run.challenges:
            sol_res = run.output_folder / ch.name / "results.toml"
            if not sol_res.is_file():
                sol_res = run.output_folder / ch.name / "results.json"
            if sol_res.is_file() and ch.name not in challenge_results:
                try:
                    content = sol_res.read_text(encoding="utf-8")
                    res_data = tomllib.loads(content) if sol_res.suffix == ".toml" else json.loads(content)
                    challenge_results[ch.name] = AndroidChallengeResult.model_validate(res_data)
                except Exception:
                    pass

        if resume_configs is not None:
            challenges_to_run = [
                ch
                for ch in run.challenges
                if ch.name in resume_configs and resume_configs[ch.name].mode != ResumeMode.NONE
            ]
        else:
            challenges_to_run = [
                ch
                for ch in run.challenges
                if ch.name not in challenge_results
                or getattr(challenge_results[ch.name], "status", None) != "completed"
            ]

    logger.info(
        "Benchmark '%s': %s (%d pending challenges, concurrency=%s, results=%s)",
        run.name,
        "resuming" if resume else "starting",
        len(challenges_to_run),
        run.num_instances if run.num_instances is not None else "auto",
        run.output_folder,
    )
    _save_benchmark_progress(run.output_folder, challenge_results, total_start)

    if challenges_to_run:
        results_lock = threading.Lock()

        def wrapped_runner(st: GlobalRunState, ch: Challenge) -> ChallengeResult:
            start_time = time.perf_counter()
            try:
                if resume:
                    cfg = resume_configs.get(ch.name) if resume_configs else None
                    try:
                        res = resume_challenge(st, ch, cfg)
                    except TypeError:
                        res = resume_challenge(st, ch)
                else:
                    res = run_challenge(st, ch)
            except Exception as exc:
                logger.exception("Challenge '%s' failed", ch.name)
                res = _failed_challenge_result(
                    run.output_folder, ch, exc, time.perf_counter() - start_time
                )
            with results_lock:
                challenge_results[ch.name] = res
                _save_benchmark_progress(run.output_folder, challenge_results, total_start)
            return res

        new_results = run_challenges(
            state,
            challenges_to_run,
            run_name=f"{run.name}{' (resumed)' if resume else ''}",
            num_instances=run.num_instances,
            challenge_runner=wrapped_runner,
        )
        challenge_results.update(new_results)

    final_result = _save_benchmark_progress(run.output_folder, challenge_results, total_start)
    logger.info(
        "Benchmark '%s': completed (score=%.4f, runtime=%.1fs)",
        run.name,
        final_result.score,
        final_result.total_runtime,
    )
    return final_result


def resume_benchmark(
    run: BenchmarkRun,
    benchmark_config: BenchmarkConfig | None = None,
    *,
    resume_configs: dict[str, ChallengeResumeConfig] | None = None,
) -> AndroidBenchmarkResult:
    return run_benchmark(
        run,
        benchmark_config=benchmark_config,
        resume=True,
        resume_configs=resume_configs,
    )


def grade_existing_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    challenge_dir = state.solutions_folder / challenge.name
    solution = challenge_dir / "solution"
    if not solution.is_dir():
        raise FileNotFoundError(f"Challenge solution directory not found: {solution}")

    transcript_path = state.solutions_folder / f"{challenge.name}_transcript.json"
    if not transcript_path.is_file():
        transcript_path = state.solutions_folder / f"{challenge.name}_transcript.jsons"
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Challenge transcript not found: {transcript_path}")

    existing_limit: str | None = None
    existing_results_file = challenge_dir / "results.toml"
    if not existing_results_file.is_file():
        existing_results_file = challenge_dir / "results.json"
    if existing_results_file.is_file():
        try:
            content = existing_results_file.read_text(encoding="utf-8")
            existing_data = tomllib.loads(content) if existing_results_file.suffix == ".toml" else json.loads(content)
            existing_limit = existing_data.get("limit_exceeded")
            if not existing_limit and isinstance(existing_data.get("score"), dict):
                existing_limit = existing_data["score"].get("limit_exceeded")
        except Exception:
            pass

    logger.info("Challenge '%s': grading existing solution (read-only)", challenge.name)
    response = extract_final_response(transcript_path)
    start_time = time.perf_counter()

    grade_solution = getattr(challenge, "grade_solution", None)
    if not callable(grade_solution):
        raise TypeError(f"Challenge {challenge.name} does not support grade_solution")

    record = grade_solution((state, solution), response, attempt=1, persist=False)
    if record.reprompt is None and record.issue_capabilities:
        record.reprompt = format_reprompt(record)

    definition = getattr(challenge, "definition", None)
    package = getattr(definition, "package", "unknown")

    overall_score, axes = calculate_scores(record)

    return AndroidChallengeResult(
        challenge=challenge.name,
        package=package,
        status="completed",
        score=FloatScore(overall_score),
        axes=axes,
        runtime=time.perf_counter() - start_time,
        limit_exceeded=existing_limit,
        attempts=[record],
    )


def run_grader(run: BenchmarkRun) -> TestGraderResult:
    logger.info(
        "Benchmark '%s': grading existing solutions (%d challenges, concurrency=%s)",
        run.name,
        len(run.challenges),
        run.num_instances if run.num_instances is not None else "auto",
    )
    state = GlobalRunState(
        sandbox_provider=DockerSandboxProvider.get(),
        cuttle_client=CuttleClient.from_config(),
        run_group=AgentGroup(run.name),
        grader_group=AgentGroup(f"{run.name} graders"),
        solutions_folder=run.output_folder,
    )
    total_start = time.perf_counter()
    challenge_results = run_challenges(
        state,
        run.challenges,
        run_name=f"{run.name} (grader)",
        num_instances=run.num_instances,
        challenge_runner=grade_existing_challenge,
    )
    def _extract_score(res: Any) -> float:
        s = getattr(res, "score", 0.0)
        if hasattr(s, "score") and not isinstance(s, (int, float)):
            return float(s.score)
        return float(s)

    scores: dict[str, float] = {
        challenge_name: _extract_score(result)
        for challenge_name, result in challenge_results.items()
    }
    reprompts: dict[str, str] = {
        challenge_name: str(getattr(result, "reprompt", ""))
        for challenge_name, result in challenge_results.items()
        if getattr(result, "reprompt", None) is not None
    }
    limits_exceeded: dict[str, str] = {
        challenge_name: limit_msg
        for challenge_name, result in challenge_results.items()
        if (limit_msg := getattr(result, "limit_exceeded", None)) is not None
    }

    total_runtime = time.perf_counter() - total_start
    overall = (
        sum(scores.values()) / len(scores)
        if scores
        else 0.0
    )
    grader_result = TestGraderResult(
        score=overall,
        total_runtime=total_runtime,
        scores=scores,
        results=challenge_results,
        reprompts=reprompts,
        limits_exceeded=limits_exceeded,
    )
    logger.info(
        "Benchmark '%s': existing solutions graded (score=%.4f, runtime=%.1fs)",
        run.name,
        grader_result.score,
        grader_result.total_runtime,
    )
    return grader_result


run_test_grader = run_grader
