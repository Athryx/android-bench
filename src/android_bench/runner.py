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

from android_bench.challenge import AndroidAppChallenge
from android_bench.grader import format_reprompt
from android_bench.models import (
    AndroidBenchmarkResult,
    AndroidChallengeResult,
    AndroidExploitScore,
    AttemptRecord,
    Capability,
    ChallengeScore,
    FloatScore,
    TestGraderResult,
    calculate_scores,
)
from android_bench.sandbox import AndroidBenchSandbox

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
    solution = state.solutions_folder / challenge.name
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
        (solution / "results.toml").write_text(init_result.model_dump_toml())

        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (solution / "results.toml").write_text(p_res.model_dump_toml())

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
    (solution / "results.toml").write_text(result.model_dump_toml())
    return result


def resume_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    solution = state.solutions_folder / challenge.name
    results_file = solution / "results.toml"
    if not results_file.is_file():
        results_file = solution / "results.json"
    transcript_file = state.solutions_folder / f"{challenge.name}_transcript.json"
    if not transcript_file.is_file():
        transcript_file = state.solutions_folder / f"{challenge.name}_transcript.jsons"

    # 1. Check if challenge is already completed
    if results_file.is_file():
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

    # 2. Check if we have an existing session to resume
    session_id: str | None = None
    if results_file.is_file():
        try:
            content = results_file.read_text(encoding="utf-8")
            data = tomllib.loads(content) if results_file.suffix == ".toml" else json.loads(content)
            session_id = data.get("session_id")
        except Exception:
            pass

    if session_id is None and transcript_file.is_file():
        try:
            for line in transcript_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if isinstance(ev, dict) and ev.get("session_id"):
                    session_id = ev["session_id"]
                    break
        except Exception:
            pass

    # Check existing graded attempts
    audit_dir = solution / "grading"
    existing_attempts: list[AttemptRecord] = []
    if audit_dir.is_dir():
        for att_path in sorted(audit_dir.glob("attempt-*.*")):
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

    num_graded = len(existing_attempts)

    # Count completed agent runs from transcript
    num_agent_runs = 0
    if transcript_file.is_file():
        try:
            for line in transcript_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if isinstance(ev, dict) and ev.get("kind") == "session_end":
                    num_agent_runs += 1
        except Exception:
            pass

    # If no session_id is known and solution doesn't exist, run fresh
    if session_id is None and not solution.is_dir():
        return run_challenge(state, challenge)

    initial_response: str | None = None
    if transcript_file.is_file() and num_agent_runs > num_graded:
        try:
            initial_response = extract_final_response(transcript_file)
        except Exception:
            initial_response = None

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

    with AndroidBenchSandbox(
        state,
        challenge.tag,
        challenge.cuttlefish_template,
        [solution_mount],
        name=challenge.name,
        internet_enabled=challenge.internet_enabled,
        extra_hosts={model_config.resolved_api_host: model_config.resolved_guest_addr},
        existing_sandbox=resumed_agent.sandbox,
        apps_to_install=(
            challenge.definition.apps_to_install
            if isinstance(challenge, AndroidAppChallenge)
            else ()
        ),
    ) as sandbox:
        logger.info("Challenge '%s': resumed solver agent ready", challenge.name)
        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (solution / "results.toml").write_text(p_res.model_dump_toml())

        outcome: Any
        try:
            with state.manage_agent(resumed_agent):
                if isinstance(challenge, AndroidAppChallenge):
                    outcome = challenge.run(
                        ChallengeInstance(solution, resumed_agent, sandbox),
                        initial_attempts=existing_attempts,
                        initial_response=initial_response,
                        start_attempt_index=num_graded,
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
                            shutil.copy2(history_file, session_transcript)
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
        limit_exceeded = getattr(outcome, "limit_exceeded", None)
        score_val = getattr(outcome, "score", 0.0)
        score_float = float(score_val.score if hasattr(score_val, "score") and not isinstance(score_val, (int, float)) else score_val)
        result = AndroidChallengeResult(
            challenge=challenge.name,
            score=FloatScore(score_float),
            axes=getattr(outcome, "axes", {}),
            runtime=time.perf_counter() - start_time,
            limit_exceeded=limit_exceeded,
            session_id=resumed_session_id,
            status="completed",
        )
    (solution / "results.toml").write_text(result.model_dump_toml())
    return result


def run_benchmark(
    run: BenchmarkRun,
    benchmark_config: BenchmarkConfig | None = None,
    *,
    resume: bool = False,
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
            if sol_res.is_file() and (
                ch.name not in challenge_results
                or getattr(challenge_results[ch.name], "status", None) != "completed"
            ):
                try:
                    content = sol_res.read_text(encoding="utf-8")
                    res_data = tomllib.loads(content) if sol_res.suffix == ".toml" else json.loads(content)
                    if res_data.get("status") == "completed" and res_data.get("score") is not None:
                        challenge_results[ch.name] = AndroidChallengeResult.model_validate(res_data)
                except Exception:
                    pass

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

    runner_func = resume_challenge if resume else run_challenge

    if challenges_to_run:
        results_lock = threading.Lock()

        def wrapped_runner(st: GlobalRunState, ch: Challenge) -> ChallengeResult:
            start_time = time.perf_counter()
            try:
                res = runner_func(st, ch)
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
) -> AndroidBenchmarkResult:
    return run_benchmark(run, benchmark_config=benchmark_config, resume=True)



def extract_final_response(transcript_path: Path) -> str:
    content = transcript_path.read_text(encoding="utf-8")
    events: list[object] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, list):
                events.extend(parsed)
            else:
                events.append(parsed)
        except json.JSONDecodeError:
            pass

    if not events:
        try:
            data = json.loads(content)
            if isinstance(data, list):
                events.extend(data)
            elif isinstance(data, dict):
                events.append(data)
        except json.JSONDecodeError:
            pass

    if not events:
        raise ValueError(f"Unable to parse transcript from {transcript_path}")

    # In multi-agent traces (Trace v2), identify the root agent (parent_agent_id is None or root_agent_id in session_info).
    root_agent_id: str | None = None
    for event in events:
        if isinstance(event, dict):
            if event.get("kind") == "agent_start" and event.get("parent_agent_id") is None:
                root_agent_id = event.get("agent_id")
                break
            if event.get("kind") == "session_info" and event.get("root_agent_id"):
                root_agent_id = event.get("root_agent_id")
                break

    def _extract_tool_text(args: object) -> str | None:
        if isinstance(args, str) and args.strip():
            return args
        if isinstance(args, dict):
            for key in ("text", "result", "output", "response"):
                val = args.get(key)
                if isinstance(val, str) and val.strip():
                    return val
            if "text" not in args and args:
                try:
                    return json.dumps(args)
                except Exception:
                    pass
        return None

    # If root_agent_id is known, check root agent's ai_text first.
    if root_agent_id is not None:
        for event in reversed(events):
            if (
                isinstance(event, dict)
                and event.get("kind") == "ai_text"
                and event.get("agent_id") == root_agent_id
            ):
                text = event.get("text")
                if isinstance(text, str) and text.strip():
                    return text

        for event in reversed(events):
            if (
                isinstance(event, dict)
                and event.get("kind") == "ai_tool_call"
                and event.get("tool_name") in ("agent_out", "submit_output")
                and event.get("agent_id") == root_agent_id
            ):
                text = _extract_tool_text(event.get("args"))
                if text:
                    return text

    for event in reversed(events):
        if isinstance(event, dict) and event.get("kind") == "ai_text":
            text = event.get("text")
            if isinstance(text, str) and text.strip():
                return text

    for event in reversed(events):
        if (
            isinstance(event, dict)
            and event.get("kind") == "ai_tool_call"
            and event.get("tool_name") in ("agent_out", "submit_output")
        ):
            text = _extract_tool_text(event.get("args"))
            if text:
                return text

    for event in reversed(events):
        if isinstance(event, dict):
            for key in ("response", "final_response", "content"):
                val = event.get(key)
                if isinstance(val, str) and val.strip():
                    return val

    raise ValueError(f"No agent response found in transcript {transcript_path}")


def grade_existing_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    solution = state.solutions_folder / challenge.name
    if not solution.is_dir():
        raise FileNotFoundError(f"Challenge solution directory not found: {solution}")

    transcript_path = state.solutions_folder / f"{challenge.name}_transcript.json"
    if not transcript_path.is_file():
        transcript_path = state.solutions_folder / f"{challenge.name}_transcript.jsons"
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Challenge transcript not found: {transcript_path}")

    existing_limit: str | None = None
    existing_results_file = solution / "results.toml"
    if not existing_results_file.is_file():
        existing_results_file = solution / "results.json"
    if existing_results_file.is_file():
        try:
            content = existing_results_file.read_text(encoding="utf-8")
            existing_data = tomllib.loads(content) if existing_results_file.suffix == ".toml" else json.loads(content)
            existing_limit = existing_data.get("limit_exceeded")
            if not existing_limit and isinstance(existing_data.get("score"), dict):
                existing_limit = existing_data["score"].get("limit_exceeded")
        except Exception:
            pass

    logger.info("Challenge '%s': grading existing solution", challenge.name)
    response = extract_final_response(transcript_path)
    start_time = time.perf_counter()

    grade_solution = getattr(challenge, "grade_solution", None)
    if not callable(grade_solution):
        raise TypeError(f"Challenge {challenge.name} does not support grade_solution")

    record = grade_solution((state, solution), response, attempt=1)
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


def run_test_grader(run: BenchmarkRun) -> TestGraderResult:
    run.output_folder.mkdir(exist_ok=True, parents=True)
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
        run_name=f"{run.name} (test-grader)",
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
    (run.output_folder / "test_grader_results.toml").write_text(
        grader_result.model_dump_toml()
    )
    logger.info(
        "Benchmark '%s': existing solutions graded (score=%.4f, runtime=%.1fs)",
        run.name,
        grader_result.score,
        grader_result.total_runtime,
    )
    return grader_result
