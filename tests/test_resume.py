import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from kbench import BenchmarkRun, ChallengeResult, GlobalRunState, Score
from kexploit_agent import Model, ModelConfig

from android_bench.challenge import AndroidAppChallenge
from android_bench.models import (
    AndroidBenchmarkResult,
    AndroidChallengeResult,
    AndroidExploitScore,
    AttemptRecord,
    Capability,
    CapabilityReview,
    CapabilityResult,
)
from android_bench.runner import (
    resume_benchmark,
    resume_challenge,
    run_benchmark,
    run_challenge,
)


class _ScoreStub(Score):
    @property
    def score(self) -> float:
        return 1.0


def _sample_exploit_score(challenge_name: str) -> AndroidExploitScore:
    review = CapabilityReview(
        attempted=True, reasoning="Clean exploit", cheating=False,
        requires_local_app=False, requires_user_interaction=False,
        declared_local_app=False, declared_user_interaction=False,
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="success")
    }
    record = AttemptRecord(
        attempt=1,
        response="Exploit ready",
        capabilities=capabilities,
        reviews={Capability.CODE_EXECUTION: review},
    )
    return AndroidExploitScore(
        challenge=challenge_name,
        package=f"com.{challenge_name}",
        attempts=[record],
    )


def test_resume_challenge_already_completed(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock()
    challenge.name = "ch_already_done"

    solution_dir = tmp_path / challenge.name
    solution_dir.mkdir()
    completed_score = _sample_exploit_score(challenge.name)
    existing_result = AndroidChallengeResult(
        score=completed_score,
        status="completed",
        current_attempt=1,
        reprompts_used=0,
        runtime=12.5,
        session_id="done_sess_1",
    )
    (solution_dir / "results.json").write_text(
        existing_result.model_dump_json(indent=2)
    )

    with (
        patch("android_bench.runner.AndroidBenchSandbox") as mock_sandbox_cls,
        patch("kexploit_agent.BaseAgent.resume") as mock_agent_resume,
    ):
        result = resume_challenge(state, challenge)

    mock_sandbox_cls.assert_not_called()
    mock_agent_resume.assert_not_called()
    assert isinstance(result, AndroidChallengeResult)
    assert result.status == "completed"
    assert result.score.score == 1.0
    assert result.issues_resolved is True


def test_resume_challenge_interrupted_grader(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock(spec=AndroidAppChallenge)
    challenge.name = "ch_grader_interrupted"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.limits = None

    solution_dir = tmp_path / challenge.name
    solution_dir.mkdir()
    (solution_dir / "results.json").write_text(
        json.dumps({
            "status": "grading",
            "session_id": "agent_finished_sess",
            "current_attempt": 1,
            "reprompts_used": 0,
        })
    )

    # Transcript contains session_end event and final response
    transcript_file = tmp_path / f"{challenge.name}_transcript.json"
    transcript_file.write_text(
        json.dumps({"kind": "session_info", "session_id": "agent_finished_sess"}) + "\n"
        + json.dumps({"kind": "ai_text", "text": "Here is my final exploit payload."}) + "\n"
        + json.dumps({"kind": "session_end"}) + "\n"
    )

    # Mock resumed agent
    mock_agent = MagicMock()
    mock_agent.session_id = "agent_finished_sess"
    mock_agent.sandbox = MagicMock()
    mock_agent.history_path = str(transcript_file)

    # Mock sandbox
    mock_sandbox_inst = MagicMock()
    mock_sandbox_inst.__enter__.return_value = mock_sandbox_inst
    mock_sandbox_inst.sandbox = mock_agent.sandbox
    mock_sandbox_inst.container_adb_host = "cuttlefish:6000"

    expected_score = _sample_exploit_score(challenge.name)
    challenge.run.return_value = expected_score

    with (
        patch("kexploit_agent.BaseAgent.resume", return_value=mock_agent) as mock_resume,
        patch("android_bench.runner.AndroidBenchSandbox", return_value=mock_sandbox_inst) as mock_sandbox_cls,
    ):
        result = resume_challenge(state, challenge)

    mock_resume.assert_called_once_with(
        "agent_finished_sess",
        history_dir=tmp_path,
        limits=None,
        delete_sandbox=False,
    )
    mock_sandbox_cls.assert_called_once()
    assert mock_sandbox_cls.call_args.kwargs["existing_sandbox"] == mock_agent.sandbox
    # challenge.run should receive initial_response extracted from transcript
    challenge.run.assert_called_once()
    call_kwargs = challenge.run.call_args.kwargs
    assert call_kwargs["initial_response"] == "Here is my final exploit payload."
    assert call_kwargs["start_attempt_index"] == 0

    assert isinstance(result, AndroidChallengeResult)
    assert result.status == "completed"
    assert (solution_dir / "results.json").is_file()
    saved = json.loads((solution_dir / "results.json").read_text())
    assert saved["status"] == "completed"


def test_resume_challenge_interrupted_agent(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock(spec=AndroidAppChallenge)
    challenge.name = "ch_agent_interrupted"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.limits = None

    solution_dir = tmp_path / challenge.name
    solution_dir.mkdir()
    (solution_dir / "results.json").write_text(
        json.dumps({
            "status": "running",
            "session_id": "interrupted_sess_1",
            "current_attempt": 1,
            "reprompts_used": 0,
        })
    )

    # Transcript has session_info but NO session_end (agent died mid-run)
    transcript_file = tmp_path / f"{challenge.name}_transcript.json"
    transcript_file.write_text(
        json.dumps({"kind": "session_info", "session_id": "interrupted_sess_1"}) + "\n"
        + json.dumps({"kind": "agent_start", "agent_id": "root"}) + "\n"
    )

    mock_agent = MagicMock()
    mock_agent.session_id = "interrupted_sess_1"
    mock_agent.sandbox = MagicMock()
    mock_agent.history_path = str(transcript_file)

    mock_sandbox_inst = MagicMock()
    mock_sandbox_inst.__enter__.return_value = mock_sandbox_inst
    mock_sandbox_inst.sandbox = mock_agent.sandbox
    mock_sandbox_inst.container_adb_host = "cuttlefish:6000"

    expected_score = _sample_exploit_score(challenge.name)
    challenge.run.return_value = expected_score

    with (
        patch("kexploit_agent.BaseAgent.resume", return_value=mock_agent) as mock_resume,
        patch("android_bench.runner.AndroidBenchSandbox", return_value=mock_sandbox_inst),
    ):
        result = resume_challenge(state, challenge)

    mock_resume.assert_called_once_with(
        "interrupted_sess_1",
        history_dir=tmp_path,
        limits=None,
        delete_sandbox=False,
    )
    # initial_response should be None since no completed session_end in transcript
    challenge.run.assert_called_once()
    assert challenge.run.call_args.kwargs["initial_response"] is None
    assert isinstance(result, AndroidChallengeResult)
    assert result.status == "completed"


def test_resume_challenge_fallback_when_resumed_agent_unavailable(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    challenge = MagicMock()
    challenge.name = "ch_fallback"

    solution_dir = tmp_path / challenge.name
    solution_dir.mkdir()
    (solution_dir / "results.json").write_text(
        json.dumps({
            "status": "running",
            "session_id": "missing_session",
        })
    )

    fresh_result = AndroidChallengeResult(
        score=_sample_exploit_score(challenge.name),
        status="completed",
        current_attempt=1,
        reprompts_used=0,
        runtime=5.0,
    )

    with (
        patch("kexploit_agent.BaseAgent.resume", side_effect=RuntimeError("container gone")),
        patch("android_bench.runner.run_challenge", return_value=fresh_result) as mock_run_challenge,
    ):
        result = resume_challenge(state, challenge)

    mock_run_challenge.assert_called_once_with(state, challenge)
    assert result == fresh_result


def test_resume_benchmark_skips_completed_and_runs_incomplete(tmp_path: Path) -> None:
    ch1 = MagicMock()
    ch1.name = "ch1"
    ch2 = MagicMock()
    ch2.name = "ch2"
    ch3 = MagicMock()
    ch3.name = "ch3"

    run = BenchmarkRun(
        name="resume-test-run",
        num_instances=1,
        challenges=[ch1, ch2, ch3],
        output_folder=tmp_path,
    )

    # ch1 is completed
    ch1_dir = tmp_path / "ch1"
    ch1_dir.mkdir()
    ch1_score = _sample_exploit_score("ch1")
    ch1_result = AndroidChallengeResult(
        score=ch1_score,
        status="completed",
        current_attempt=1,
        reprompts_used=0,
        runtime=10.0,
    )
    (ch1_dir / "results.json").write_text(ch1_result.model_dump_json(indent=2))

    # ch2 is incomplete
    ch2_dir = tmp_path / "ch2"
    ch2_dir.mkdir()
    (ch2_dir / "results.json").write_text(
        json.dumps({"status": "running", "current_attempt": 1})
    )

    ch2_score = _sample_exploit_score("ch2")
    ch2_resumed_result = AndroidChallengeResult(
        score=ch2_score,
        status="completed",
        current_attempt=1,
        reprompts_used=0,
        runtime=8.0,
    )
    ch3_score = _sample_exploit_score("ch3")
    ch3_fresh_result = AndroidChallengeResult(
        score=ch3_score,
        status="completed",
        current_attempt=1,
        reprompts_used=0,
        runtime=9.0,
    )

    def fake_resume_challenge(st: GlobalRunState, ch: MagicMock) -> AndroidChallengeResult:
        if ch.name == "ch2":
            return ch2_resumed_result
        if ch.name == "ch3":
            return ch3_fresh_result
        return ch1_result

    with (
        patch("android_bench.runner.DockerSandboxProvider"),
        patch("android_bench.runner.CuttleClient"),
        patch("android_bench.runner.resume_challenge", side_effect=fake_resume_challenge) as mock_res_ch,
    ):
        final_result = resume_benchmark(run)

    assert isinstance(final_result, AndroidBenchmarkResult)
    # ch1 was NOT passed to resume_challenge because it was already completed!
    called_names = [call.args[1].name for call in mock_res_ch.call_args_list]
    assert "ch1" not in called_names
    assert "ch2" in called_names
    assert "ch3" in called_names

    # All 3 challenges are in finished_challenges
    assert set(final_result.finished_challenges) == {"ch1", "ch2", "ch3"}
    assert "ch1" in final_result.scores
    assert "ch2" in final_result.scores
    assert "ch3" in final_result.scores

    # Check root results.json
    root_json = json.loads((tmp_path / "results.json").read_text())
    assert "finished_challenges" not in root_json
    assert "scores" not in root_json
    assert "limits_exceeded" not in root_json
    assert root_json["results"]["ch1"]["status"] == "completed"
    assert root_json["results"]["ch2"]["status"] == "completed"
    assert root_json["results"]["ch3"]["status"] == "completed"
