from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

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
from android_bench.grader import format_reprompt, get_attempt_issues
from android_bench.models import (
    AndroidBenchmarkResult,
    AndroidChallengeResult,
    AndroidExploitScore,
    AttemptRecord,
    Capability,
    TestGraderResult,
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
    challenge_results: dict[str, ChallengeResult],
    total_start: float,
) -> AndroidBenchmarkResult:
    scores: dict[str, Score] = {
        challenge_name: result.score
        for challenge_name, result in challenge_results.items()
        if result.score is not None
    }
    limits_exceeded: dict[str, str] = {
        challenge_name: limit_msg
        for challenge_name, result in challenge_results.items()
        if (limit_msg := getattr(result, "limit_exceeded", None)) is not None
    }
    finished_challenges: list[str] = [
        challenge_name
        for challenge_name, result in challenge_results.items()
        if getattr(result, "status", None) == "completed"
        or (
            result.score is not None
            and getattr(result.score, "disclosure_resolved", None) is not None
        )
    ]
    total_runtime = time.perf_counter() - total_start
    overall = (
        sum(s.score for s in scores.values()) / len(scores) if scores else 0.0
    )
    benchmark_result = AndroidBenchmarkResult(
        overall_score=overall,
        total_runtime=total_runtime,
        scores=scores,
        results=challenge_results,
        limits_exceeded=limits_exceeded,
        finished_challenges=finished_challenges,
    )
    (output_folder / "results.json").write_text(
        benchmark_result.model_dump_json(indent=2)
    )
    return benchmark_result


def run_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
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
    ) as sandbox:
        if sandbox.sandbox is None:
            raise RuntimeError("solver Docker sandbox is not running")
        ch_limits = getattr(challenge, "limits", None)
        agent_limits = ch_limits if isinstance(ch_limits, Limits) else None
        agent = challenge.harness.create_agent(
            f"{challenge.name}_agent",
            model_config,
            challenge.system_prompt(sandbox.container_adb_host),
            sandbox.sandbox,
            agent_group=state.run_group,
            limits=agent_limits,
        )
        raw_sid = getattr(agent, "session_id", None)
        session_id: str | None = (
            str(raw_sid) if isinstance(raw_sid, (str, Path)) else None
        )
        init_result = AndroidChallengeResult(
            score=None,
            session_id=session_id,
            status="running",
            current_attempt=1,
            reprompts_used=0,
            runtime=0.0,
        )
        (solution / "results.json").write_text(init_result.model_dump_json(indent=2))

        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (solution / "results.json").write_text(p_res.model_dump_json(indent=2))

        score: Score
        try:
            with state.manage_agent(agent):
                if isinstance(challenge, AndroidAppChallenge):
                    score = challenge.run(
                        ChallengeInstance(solution, agent, sandbox),
                        progress_callback=on_progress,
                    )
                else:
                    score = challenge.run(ChallengeInstance(solution, agent, sandbox))
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

    limit_exceeded = getattr(score, "limit_exceeded", None)
    result = AndroidChallengeResult(
        score=score,
        runtime=time.perf_counter() - start_time,
        limit_exceeded=limit_exceeded,
        session_id=session_id,
        status="completed",
        current_attempt=len(getattr(score, "attempts", [])) or 1,
        reprompts_used=getattr(score, "reprompts_used", 0),
    )
    (solution / "results.json").write_text(result.model_dump_json(indent=2))
    return result


def resume_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    solution = state.solutions_folder / challenge.name
    results_file = solution / "results.json"
    transcript_file = state.solutions_folder / f"{challenge.name}_transcript.json"
    if not transcript_file.is_file():
        transcript_file = state.solutions_folder / f"{challenge.name}_transcript.jsons"

    # 1. Check if challenge is already completed
    if results_file.is_file():
        try:
            data = json.loads(results_file.read_text())
            if data.get("status") == "completed" and data.get("score") is not None:
                return AndroidChallengeResult.model_validate(data)
            if data.get("score") is not None and isinstance(data.get("score"), dict):
                if data["score"].get("disclosure_resolved") is not None:
                    return AndroidChallengeResult.model_validate(data)
        except Exception:
            pass

    # 2. Check if we have an existing session to resume
    session_id: str | None = None
    if results_file.is_file():
        try:
            data = json.loads(results_file.read_text())
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
        for att_path in sorted(audit_dir.glob("attempt-*.json")):
            try:
                existing_attempts.append(
                    AttemptRecord.model_validate_json(att_path.read_text())
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
    ) as sandbox:
        def on_progress(p_res: AndroidChallengeResult) -> None:
            p_res.runtime = time.perf_counter() - start_time
            (solution / "results.json").write_text(p_res.model_dump_json(indent=2))

        score: Score
        try:
            with state.manage_agent(resumed_agent):
                if isinstance(challenge, AndroidAppChallenge):
                    score = challenge.run(
                        ChallengeInstance(solution, resumed_agent, sandbox),
                        initial_attempts=existing_attempts,
                        initial_response=initial_response,
                        start_attempt_index=num_graded,
                        progress_callback=on_progress,
                    )
                else:
                    score = challenge.run(
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

    limit_exceeded = getattr(score, "limit_exceeded", None)
    raw_resumed_sid = getattr(resumed_agent, "session_id", None)
    resumed_session_id = (
        str(raw_resumed_sid)
        if isinstance(raw_resumed_sid, (str, Path))
        else None
    )
    result = AndroidChallengeResult(
        score=score,
        runtime=time.perf_counter() - start_time,
        limit_exceeded=limit_exceeded,
        session_id=resumed_session_id,
        status="completed",
        current_attempt=len(getattr(score, "attempts", [])) or 1,
        reprompts_used=getattr(score, "reprompts_used", 0),
    )
    (solution / "results.json").write_text(result.model_dump_json(indent=2))
    return result


def run_benchmark(
    run: BenchmarkRun,
    benchmark_config: BenchmarkConfig | None = None,
    *,
    resume: bool = False,
) -> BenchmarkResult:
    run.output_folder.mkdir(exist_ok=True, parents=True)
    if benchmark_config is not None:
        (run.output_folder / "challenge.json").write_text(
            benchmark_config.formatted_json()
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
        results_file = run.output_folder / "results.json"
        if results_file.is_file():
            try:
                existing_data = json.loads(results_file.read_text())
                if "results" in existing_data and isinstance(existing_data["results"], dict):
                    for name, res_data in existing_data["results"].items():
                        challenge_results[name] = AndroidChallengeResult.model_validate(res_data)
            except Exception:
                pass

        for ch in run.challenges:
            sol_res = run.output_folder / ch.name / "results.json"
            if sol_res.is_file() and (
                ch.name not in challenge_results
                or getattr(challenge_results[ch.name], "status", None) != "completed"
            ):
                try:
                    res_data = json.loads(sol_res.read_text())
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

    _save_benchmark_progress(run.output_folder, challenge_results, total_start)

    runner_func = resume_challenge if resume else run_challenge

    if challenges_to_run:
        results_lock = threading.Lock()

        def wrapped_runner(st: GlobalRunState, ch: Challenge) -> ChallengeResult:
            res = runner_func(st, ch)
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
    return final_result


def resume_benchmark(
    run: BenchmarkRun,
    benchmark_config: BenchmarkConfig | None = None,
) -> BenchmarkResult:
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
    existing_results_file = solution / "results.json"
    if existing_results_file.is_file():
        try:
            existing_data = json.loads(existing_results_file.read_text())
            existing_limit = existing_data.get("limit_exceeded")
            if not existing_limit and isinstance(existing_data.get("score"), dict):
                existing_limit = existing_data["score"].get("limit_exceeded")
        except Exception:
            pass

    response = extract_final_response(transcript_path)
    start_time = time.perf_counter()

    grade_solution = getattr(challenge, "grade_solution", None)
    if not callable(grade_solution):
        raise TypeError(f"Challenge {challenge.name} does not support grade_solution")

    graded, record = grade_solution((state, solution), response, attempt=1)

    definition = getattr(challenge, "definition", None)
    package = getattr(definition, "package", "unknown")

    attempted: set[Capability] = getattr(graded, "attempted", set())
    issues = get_attempt_issues(
        graded.capabilities, graded.assessment, attempted
    )

    if not issues:
        score = AndroidExploitScore(
            challenge=challenge.name,
            package=package,
            capabilities=graded.capabilities,
            assessment=graded.assessment,
            attempts=[record],
            reprompts_used=0,
            disclosure_resolved=True,
            reprompt=None,
            limit_exceeded=existing_limit,
        )
    else:
        reprompt_msg = format_reprompt(
            graded.capabilities, graded.assessment, attempted
        )
        score = AndroidExploitScore(
            challenge=challenge.name,
            package=package,
            capabilities=graded.capabilities,
            assessment=graded.assessment,
            attempts=[record],
            reprompts_used=0,
            disclosure_resolved=False,
            reprompt=reprompt_msg,
            limit_exceeded=existing_limit,
        )

    return AndroidChallengeResult(
        score=score,
        runtime=time.perf_counter() - start_time,
        limit_exceeded=existing_limit,
    )


def run_test_grader(run: BenchmarkRun) -> TestGraderResult:
    run.output_folder.mkdir(exist_ok=True, parents=True)
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
    scores: dict[str, Score] = {
        challenge_name: result.score
        for challenge_name, result in challenge_results.items()
    }
    reprompts: dict[str, str] = {
        challenge_name: result.score.reprompt
        for challenge_name, result in challenge_results.items()
        if isinstance(result.score, AndroidExploitScore) and result.score.reprompt is not None
    }
    limits_exceeded: dict[str, str] = {
        challenge_name: limit_msg
        for challenge_name, result in challenge_results.items()
        if (limit_msg := getattr(result, "limit_exceeded", None)) is not None
    }

    total_runtime = time.perf_counter() - total_start
    overall = (
        sum(result.score.score for result in challenge_results.values())
        / len(challenge_results)
        if challenge_results
        else 0.0
    )
    grader_result = TestGraderResult(
        overall_score=overall,
        total_runtime=total_runtime,
        scores=scores,
        results=challenge_results,
        reprompts=reprompts,
        limits_exceeded=limits_exceeded,
    )
    (run.output_folder / "test_grader_results.json").write_text(
        grader_result.model_dump_json(indent=2)
    )
    return grader_result

