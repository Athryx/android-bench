from __future__ import annotations

import shutil
import time
from pathlib import Path

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
from kexploit_agent import AgentGroup, summarize_log
from ksandbox import DockerSandboxProvider, MountInfo

from android_bench.sandbox import AndroidBenchSandbox


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
        agent = challenge.harness.create_agent(
            f"{challenge.name}_agent",
            model_config,
            challenge.system_prompt(sandbox.container_adb_host),
            sandbox.sandbox,
            agent_group=state.run_group,
        )
        try:
            with state.manage_agent(agent):
                score = challenge.run(ChallengeInstance(solution, agent, sandbox))
        finally:
            history_path = getattr(agent, "history_path", None)
            if isinstance(history_path, (str, Path)):
                history_file = Path(history_path)
                if history_file.is_file():
                    if getattr(challenge, "summarize", False) is True:
                        summarize_log(history_file)
                    shutil.copy2(history_file, solution / "agent_transcript.jsons")

    result = ChallengeResult(score=score, runtime=time.perf_counter() - start_time)
    (solution / "results.json").write_text(result.model_dump_json(indent=2))
    return result


def run_benchmark(run: BenchmarkRun) -> BenchmarkResult:
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
        run_name=run.name,
        num_instances=run.num_instances,
        challenge_runner=run_challenge,
    )
    scores: dict[str, Score] = {
        challenge_name: result.score
        for challenge_name, result in challenge_results.items()
    }

    total_runtime = time.perf_counter() - total_start
    overall = (
        sum(result.score.score for result in challenge_results.values())
        / len(challenge_results)
        if challenge_results
        else 0.0
    )
    benchmark_result = BenchmarkResult(
        overall_score=overall,
        total_runtime=total_runtime,
        scores=scores,
        results=challenge_results,
    )
    (run.output_folder / "results.json").write_text(
        benchmark_result.model_dump_json(indent=2)
    )
    return benchmark_result
