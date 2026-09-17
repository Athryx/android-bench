from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cuttle_cli import CuttleClient
from kbench import (
    BenchmarkResult,
    BenchmarkRun,
    Challenge,
    ChallengeInstance,
    ChallengeResult,
    GlobalRunState,
    Score,
)
from kexploit_agent import AgentGroup
from ksandbox import DockerSandboxProvider, MountInfo

from android_bench.sandbox import AndroidBenchSandbox

logger = logging.getLogger(__name__)


def run_challenge(state: GlobalRunState, challenge: Challenge) -> ChallengeResult:
    solution = state.solutions_folder / challenge.name
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
        score = challenge.run(ChallengeInstance(solution, agent, sandbox))

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
    challenge_results: dict[str, ChallengeResult] = {}
    scores: dict[str, Score] = {}
    total_start = time.perf_counter()
    max_workers = run.num_instances if run.num_instances and run.num_instances > 0 else None
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_challenge, state, challenge): challenge
            for challenge in run.challenges
        }
        for future in as_completed(futures):
            challenge = futures[future]
            result = future.result()
            challenge_results[challenge.name] = result
            scores[challenge.name] = result.score
            logger.info(
                "Challenge %s finished in %.2fs with score %.4f",
                challenge.name,
                result.runtime,
                result.score.score,
            )

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
