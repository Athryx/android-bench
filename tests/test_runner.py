import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from kbench import BenchmarkRun, ChallengeResult, GlobalRunState, Score
from kexploit_agent import Model, ModelConfig

from android_bench.models import (
    AndroidExploitScore,
    AttemptRecord,
    Capability,
    CapabilityReview,
    CapabilityResult,
)
from android_bench.runner import (
    extract_final_response,
    grade_existing_challenge,
    run_benchmark,
    run_challenge,
    run_test_grader,
)


class _Score(Score):
    @property
    def score(self) -> float:
        return 1.0


def review(
    *,
    requires_local_app: bool,
    requires_user_interaction: bool,
    cheating: bool,
    reason: str,
    declared_local_app: bool | None = None,
    declared_user_interaction: bool | None = None,
) -> CapabilityReview:
    return CapabilityReview(
        attempted=True,
        reasoning=reason,
        cheating=cheating,
        requires_local_app=requires_local_app,
        requires_user_interaction=requires_user_interaction,
        declared_local_app=declared_local_app,
        declared_user_interaction=declared_user_interaction,
    )


def test_run_challenge_passes_internet_setting_to_sandbox(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "internet-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = True
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    container = MagicMock()
    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = container
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox) as cls:
        result = run_challenge(state, challenge)

    assert result.score.score == 1.0
    cls.assert_called_once_with(
        state,
        "android-bench:test",
        "challenge6",
        cls.call_args.args[3],
        name="internet-test",
        internet_enabled=True,
        extra_hosts={"api.openai.com": "127.0.0.1"},
    )


def test_run_challenge_copies_agent_history(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "transcript-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history.jsons"
    history_file.write_text('{"event": "init"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        result = run_challenge(state, challenge)

    assert result.score.score == 1.0
    solution_dir = tmp_path / "transcript-test"
    assert (solution_dir / "results.json").is_file()
    assert (tmp_path / "transcript-test_transcript.json").is_file()
    assert (tmp_path / "transcript-test_transcript.json").read_text() == '{"event": "init"}\n'
    assert not (solution_dir / "agent_transcript.jsons").exists()


def test_run_challenge_copies_agent_history_and_context(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "context-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history.jsons"
    history_file.write_text('{"event": "init"}\n')
    context_file = tmp_path / "raw_history.context.jsonl"
    context_file.write_text('{"kind": "request", "model": "gpt-6"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        result = run_challenge(state, challenge)

    assert result.score.score == 1.0
    assert (tmp_path / "context-test_transcript.json").is_file()
    assert (tmp_path / "context-test_transcript.json").read_text() == '{"event": "init"}\n'
    assert (tmp_path / "context-test_transcript.context.jsonl").is_file()
    assert (
        tmp_path / "context-test_transcript.context.jsonl"
    ).read_text() == '{"kind": "request", "model": "gpt-6"}\n'


def test_run_challenge_summarizes_agent_history_before_copy(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "summary-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.summarize = True
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history_summary.jsons"
    history_file.write_text('{"event": "init"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    def summarize(path: Path) -> None:
        path.write_text(path.read_text() + '{"event": "summary"}\n')

    with (
        patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox),
        patch("android_bench.runner.summarize_log", side_effect=summarize) as summarize_log,
    ):
        run_challenge(state, challenge)

    expected = '{"event": "init"}\n{"event": "summary"}\n'
    summarize_log.assert_called_once_with(history_file)
    assert history_file.read_text() == expected
    assert (tmp_path / "summary-test_transcript.json").read_text() == expected
    assert not (tmp_path / "summary-test" / "agent_transcript.jsons").exists()


def test_run_challenge_copies_agent_history_on_failure(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "transcript-failure-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.side_effect = RuntimeError("challenge run failed")

    history_file = tmp_path / "raw_history_failure.jsons"
    history_file.write_text('{"event": "crashed"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    import pytest

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        with pytest.raises(RuntimeError, match="challenge run failed"):
            run_challenge(state, challenge)

    solution_dir = tmp_path / "transcript-failure-test"
    assert (tmp_path / "transcript-failure-test_transcript.json").is_file()
    assert (tmp_path / "transcript-failure-test_transcript.json").read_text() == '{"event": "crashed"}\n'
    assert not (solution_dir / "agent_transcript.jsons").exists()


def test_run_challenge_calls_prepare_solution(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "prepare-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        run_challenge(state, challenge)

    challenge.prepare_solution.assert_called_once_with(tmp_path / "prepare-test")


def test_extract_final_response_jsonl(tmp_path: Path) -> None:
    transcript = tmp_path / "test_transcript.json"
    transcript.write_text(
        '{"kind": "human_message", "text": "start"}\n'
        '{"kind": "ai_text", "text": "intermediate thought"}\n'
        '{"kind": "tool_result", "text": "ok"}\n'
        '{"kind": "ai_text", "text": "final solution response"}\n'
    )
    assert extract_final_response(transcript) == "final solution response"


def test_extract_final_response_json_array(tmp_path: Path) -> None:
    transcript = tmp_path / "test_transcript.json"
    transcript.write_text(
        '[{"kind": "ai_text", "text": "first"}, {"kind": "ai_text", "text": "second"}]'
    )
    assert extract_final_response(transcript) == "second"


def test_extract_final_response_empty_or_missing(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.json"
    transcript.write_text('{"kind": "tool_result", "text": "ok"}\n')
    with pytest.raises(ValueError, match="No agent response found"):
        extract_final_response(transcript)


def test_extract_final_response_multi_agent(tmp_path: Path) -> None:
    transcript = tmp_path / "multi_agent_transcript.json"
    transcript.write_text(
        '{"seq": 1, "kind": "session_start", "trace_version": 2}\n'
        '{"seq": 2, "kind": "agent_start", "agent_id": "root-1", "agent_name": "solver", "parent_agent_id": null}\n'
        '{"seq": 3, "kind": "agent_start", "agent_id": "sub-1", "agent_name": "researcher", "parent_agent_id": "root-1"}\n'
        '{"seq": 4, "kind": "ai_text", "agent_id": "root-1", "text": "root final solution"}\n'
        '{"seq": 5, "kind": "ai_text", "agent_id": "sub-1", "text": "subagent research output"}\n'
        '{"seq": 6, "kind": "agent_end", "agent_id": "sub-1"}\n'
        '{"seq": 7, "kind": "agent_end", "agent_id": "root-1"}\n'
        '{"seq": 8, "kind": "session_end"}\n'
    )
    # Must return the root agent's response, not the subagent's later response
    assert extract_final_response(transcript) == "root final solution"


def test_extract_final_response_multi_agent_agent_out(tmp_path: Path) -> None:
    transcript = tmp_path / "agent_out_transcript.json"
    transcript.write_text(
        '{"seq": 1, "kind": "session_start", "trace_version": 2}\n'
        '{"seq": 2, "kind": "agent_start", "agent_id": "root-1", "agent_name": "solver", "parent_agent_id": null}\n'
        '{"seq": 3, "kind": "ai_tool_call", "agent_id": "root-1", "tool_name": "agent_out", "args": {"text": "output via agent_out"}}\n'
        '{"seq": 4, "kind": "agent_end", "agent_id": "root-1"}\n'
        '{"seq": 5, "kind": "session_end"}\n'
    )
    assert extract_final_response(transcript) == "output via agent_out"


def test_extract_final_response_submit_output(tmp_path: Path) -> None:
    transcript = tmp_path / "submit_output_transcript.json"
    transcript.write_text(
        '{"seq": 1, "kind": "session_info", "root_agent_id": "root-1"}\n'
        '{"seq": 2, "kind": "agent_start", "agent_id": "root-1", "agent_name": "solver", "parent_agent_id": null}\n'
        '{"seq": 3, "kind": "ai_tool_call", "agent_id": "root-1", "tool_name": "submit_output", "args": {"result": "output via submit_output"}}\n'
        '{"seq": 4, "kind": "agent_end", "agent_id": "root-1"}\n'
        '{"seq": 5, "kind": "session_end"}\n'
    )
    assert extract_final_response(transcript) == "output via submit_output"


def test_extract_final_response_session_info_root_agent(tmp_path: Path) -> None:
    transcript = tmp_path / "session_info_transcript.json"
    transcript.write_text(
        '{"seq": 1, "kind": "session_info", "root_agent_id": "custom-root"}\n'
        '{"seq": 2, "kind": "agent_start", "agent_id": "child-1", "parent_agent_id": "custom-root"}\n'
        '{"seq": 3, "kind": "ai_text", "agent_id": "child-1", "text": "child text"}\n'
        '{"seq": 4, "kind": "ai_text", "agent_id": "custom-root", "text": "root final text"}\n'
        '{"seq": 5, "kind": "session_end"}\n'
    )
    assert extract_final_response(transcript) == "root final text"


def test_extract_final_response_with_summaries(tmp_path: Path) -> None:
    transcript = tmp_path / "summarized_transcript.json"
    transcript.write_text(
        '{"seq": 1, "kind": "session_start", "trace_version": 2}\n'
        '{"seq": 2, "kind": "agent_start", "agent_id": "root-1", "agent_name": "solver", "parent_agent_id": null}\n'
        '{"seq": 3, "kind": "ai_text", "agent_id": "root-1", "text": "root final response"}\n'
        '{"seq": 4, "kind": "agent_end", "agent_id": "root-1"}\n'
        '{"seq": 5, "kind": "session_end"}\n'
        '{"seq": 6, "kind": "agent_summary", "agent_id": "root-1", "summary": "Root summary text"}\n'
        '{"seq": 7, "kind": "session_summary", "summary": "Session summary text"}\n'
    )
    # Must ignore post-processing summaries and return the root agent's response
    assert extract_final_response(transcript) == "root final response"


def test_run_challenge_copies_history_even_if_summarize_fails(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "summary-fail-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.summarize = True
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history_summary_fail.jsons"
    history_file.write_text('{"event": "init"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with (
        patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox),
        patch("android_bench.runner.summarize_log", side_effect=RuntimeError("summarizer failed")),
    ):
        with pytest.raises(RuntimeError, match="summarizer failed"):
            run_challenge(state, challenge)

    # History must still be copied despite summarizer failure
    assert (tmp_path / "summary-fail-test_transcript.json").is_file()
    assert (tmp_path / "summary-fail-test_transcript.json").read_text() == '{"event": "init"}\n'


def test_grade_existing_challenge_jsons_fallback(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    sol_dir = tmp_path / "jsons-ch"
    sol_dir.mkdir()
    # Write to .jsons instead of .json
    transcript = tmp_path / "jsons-ch_transcript.jsons"
    transcript.write_text('{"kind": "ai_text", "text": "working exploit"}\n')

    challenge = MagicMock()
    challenge.name = "jsons-ch"
    challenge.definition.package = "com.test.app"

    capability_review = review(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="clean exploit",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
    }
    record = AttemptRecord(
        attempt=1,
        response="working exploit",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.issues_resolved is True
    assert result.score.score == 1.0


def test_grade_existing_challenge_matching_disclosure(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    sol_dir = tmp_path / "test-ch"
    sol_dir.mkdir()
    transcript = tmp_path / "test-ch_transcript.json"
    transcript.write_text('{"kind": "ai_text", "text": "working exploit"}\n')

    challenge = MagicMock()
    challenge.name = "test-ch"
    challenge.definition.package = "com.test.app"

    capability_review = review(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="clean exploit",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
    }
    record = AttemptRecord(
        attempt=1,
        response="working exploit",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.issues_resolved is True
    assert result.score.reprompt is None
    assert result.score.score == 1.0
    challenge.grade_solution.assert_called_once_with(
        (state, sol_dir), "working exploit", attempt=1
    )


def test_grade_existing_challenge_reprompt_on_mismatch(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    sol_dir = tmp_path / "mismatch-ch"
    sol_dir.mkdir()
    transcript = tmp_path / "mismatch-ch_transcript.json"
    transcript.write_text('{"kind": "ai_text", "text": "undisclosed exploit"}\n')

    challenge = MagicMock()
    challenge.name = "mismatch-ch"
    challenge.definition.package = "com.test.mismatch"

    capability_review = review(
        requires_local_app=True,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="undeclared local app",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
    }
    record = AttemptRecord(
        attempt=1,
        response="undisclosed exploit",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.issues_resolved is False
    assert result.score.score == 0.0
    assert result.score.reprompt is not None
    assert "- Local app: Mismatch (declared `False`, observed `True`)." in result.score.reprompt
    assert "- User interaction: Matches the declared requirement (`False`)." in result.score.reprompt


def test_grade_existing_challenge_missing_files_raises(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock()
    challenge.name = "missing-ch"

    with pytest.raises(FileNotFoundError, match="solution directory not found"):
        grade_existing_challenge(state, challenge)

    (tmp_path / "missing-ch").mkdir()
    with pytest.raises(FileNotFoundError, match="transcript not found"):
        grade_existing_challenge(state, challenge)


def test_run_test_grader(tmp_path: Path) -> None:
    challenge = MagicMock()
    challenge.name = "ch1"
    run = BenchmarkRun(
        name="test-run",
        num_instances=1,
        challenges=[challenge],
        output_folder=tmp_path,
    )

    fake_result = ChallengeResult(score=_Score(), runtime=1.5)
    with patch(
        "android_bench.runner.run_challenges", return_value={"ch1": fake_result}
    ):
        result = run_test_grader(run)

    assert result.overall_score == 1.0
    assert (tmp_path / "test_grader_results.json").is_file()
    assert not (tmp_path / "results.json").exists()


def test_grade_existing_challenge_reprompt_on_failed_attempted_poc(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    sol_dir = tmp_path / "failed-poc-ch"
    sol_dir.mkdir()
    transcript = tmp_path / "failed-poc-ch_transcript.json"
    transcript.write_text('{"kind": "ai_text", "text": "exploit response"}\n')

    challenge = MagicMock()
    challenge.name = "failed-poc-ch"
    challenge.definition.package = "com.test.failedpoc"

    capability_review = review(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="clean remote exploit attempt",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(
            passed=False,
            detail="process did not start",
            exit_code=1,
            stdout="fail",
            stderr="err",
            logcat="crash",
        )
    }
    record = AttemptRecord(
        attempt=1,
        attempted_pocs={Capability.CODE_EXECUTION},
        response="exploit response",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.issues_resolved is False
    assert result.score.score == 0.0
    assert result.score.reprompt is not None
    assert "### `code_execution`" in result.score.reprompt
    assert "- PoC: failed — process did not start" in result.score.reprompt
    assert "process did not start" in result.score.reprompt


def test_grade_existing_challenge_reprompt_on_cheating(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    sol_dir = tmp_path / "cheating-ch"
    sol_dir.mkdir()
    transcript = tmp_path / "cheating-ch_transcript.json"
    transcript.write_text('{"kind": "ai_text", "text": "cheating exploit"}\n')

    challenge = MagicMock()
    challenge.name = "cheating-ch"
    challenge.definition.package = "com.test.cheating"

    capability_review = review(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=True,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="used root su",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
    }
    record = AttemptRecord(
        attempt=1,
        attempted_pocs={Capability.CODE_EXECUTION},
        response="cheating exploit",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.issues_resolved is False
    assert result.score.score == 0.0
    assert result.score.reprompt is not None
    assert "- Cheating: Detected." in result.score.reprompt
    assert "Grader reasoning: used root su" in result.score.reprompt
    assert "- Local app: Matches the declared requirement (`False`)." in result.score.reprompt


def test_run_challenge_passes_limits_and_records_limit_exceeded(tmp_path: Path) -> None:
    from kexploit_agent import Limits
    from android_bench.models import AndroidChallengeResult

    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "limits-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.limits = Limits(turn_limit=5)
    challenge.system_prompt.return_value = "test prompt"

    score = AndroidExploitScore(
        challenge="limits-test",
        package="com.test",
        attempts=[AttemptRecord(attempt=1, response="", capabilities={}, reviews={})],
        limit_exceeded="turn_limit limit reached (5)",
    )
    challenge.run.return_value = score

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        result = run_challenge(state, challenge)

    challenge.harness.create_agent.assert_called_once_with(
        "limits-test_agent",
        challenge.model_config,
        "test prompt",
        sandbox.sandbox,
        agent_group=state.run_group,
        limits=challenge.limits,
    )
    assert isinstance(result, AndroidChallengeResult)
    assert result.limit_exceeded == "turn_limit limit reached (5)"
    solution_dir = tmp_path / "limits-test"
    res_json = (solution_dir / "results.json").read_text()
    assert '"limit_exceeded": "turn_limit limit reached (5)"' in res_json


def test_run_benchmark_aggregates_limits_exceeded(tmp_path: Path) -> None:
    from android_bench.models import AndroidBenchmarkResult, AndroidChallengeResult

    run = MagicMock(spec=BenchmarkRun)
    run.name = "test_run"
    run.output_folder = tmp_path
    run.challenges = [MagicMock(), MagicMock()]
    run.num_instances = None

    cr1 = AndroidChallengeResult(score=_Score(), runtime=10.0, limit_exceeded="turn_limit limit reached (5)")
    cr2 = AndroidChallengeResult(score=_Score(), runtime=15.0, limit_exceeded=None)

    with patch(
        "android_bench.runner.run_challenges",
        return_value={"ch1": cr1, "ch2": cr2},
    ):
        benchmark_result = run_benchmark(run)

    assert isinstance(benchmark_result, AndroidBenchmarkResult)
    assert benchmark_result.limits_exceeded == {"ch1": "turn_limit limit reached (5)"}
    saved_json = (tmp_path / "results.json").read_text()
    assert '"limits_exceeded": {\n    "ch1": "turn_limit limit reached (5)"\n  }' in saved_json


def test_grade_existing_challenge_preserves_limit_exceeded(tmp_path: Path) -> None:
    from android_bench.models import AndroidChallengeResult

    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock()
    challenge.name = "existing_limit_ch"
    challenge.definition = MagicMock()
    challenge.definition.package = "com.test"

    solution_dir = tmp_path / challenge.name
    solution_dir.mkdir()
    (solution_dir / "results.json").write_text(
        json.dumps({"limit_exceeded": "time_limit limit reached (300)"})
    )
    transcript = tmp_path / f"{challenge.name}_transcript.json"
    transcript.write_text(json.dumps({"kind": "ai_text", "text": "poc report"}) + "\n")

    capability_review = review(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        reason="Clean",
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
    }
    record = AttemptRecord(
        attempt=1,
        attempted_pocs={Capability.CODE_EXECUTION},
        response="poc report",
        capabilities=capabilities,
        reviews={cap: capability_review for cap in capabilities},
    )
    challenge.grade_solution.return_value = record

    result = grade_existing_challenge(state, challenge)
    assert isinstance(result, AndroidChallengeResult)
    assert result.limit_exceeded == "time_limit limit reached (300)"
    assert isinstance(result.score, AndroidExploitScore)
    assert result.score.limit_exceeded == "time_limit limit reached (300)"
