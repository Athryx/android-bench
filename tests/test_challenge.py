from pathlib import Path
from typing import Any, cast

import pytest
from kbench import ChallengeInstance
from kexploit_agent import HarnessType, Model, ModelConfig

from android_bench.catalog import load_catalog
from android_bench.challenge import AndroidAppChallenge
from android_bench.models import AttemptRecord, Capability, CapabilityReview, CapabilityResult

CHALLENGES = load_catalog().defaults


class FakeAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.closed = False

    def run(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"response {len(self.prompts)}"

    def close(self) -> None:
        self.closed = True


def make_review(matches: bool) -> CapabilityReview:
    return CapabilityReview(
        attempted=True,
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False if matches else True,
        declared_user_interaction=False,
        reasoning="test",
    )


def reviews_for(
    capabilities: dict[Capability, CapabilityResult], matches: bool
) -> dict[Capability, CapabilityReview]:
    return {
        cap: (
            make_review(matches)
            if result.passed
            else CapabilityReview(attempted=False, reasoning="No success claim")
        )
        for cap, result in capabilities.items()
    }


def test_mismatch_reprompts_and_regrades_fresh(
    monkeypatch: Any, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        calls.append(attempt)
        capabilities = {
            item: CapabilityResult(passed=item is Capability.FILE_READ, detail="test")
            for item in Capability
        }
        return AttemptRecord(attempt=attempt, response=response, capabilities=capabilities, reviews=reviews_for(capabilities, matches=attempt == 2))

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = FakeAgent()
    instance = ChallengeInstance(
        solution=tmp_path / "solution",
        agent=cast(Any, agent),
        sandbox=cast(Any, object()),
    )
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        max_reprompts=2,
    )
    with caplog.at_level("INFO", logger="android_bench.challenge"):
        score = challenge.run(instance)

    assert calls == [1, 2]
    assert len(agent.prompts) == 2
    assert agent.closed
    assert score.reprompts_used == 1
    assert score.issues_resolved
    assert (tmp_path / "grading" / "attempt-1.toml").is_file()
    assert (tmp_path / "grading" / "attempt-2.toml").is_file()
    assert not (tmp_path / "solution" / "grading").exists()
    messages = [record.message for record in caplog.records]
    assert messages.index(
        f"Challenge '{challenge.name}': initial agent run started (attempt=1)"
    ) < messages.index(
        f"Challenge '{challenge.name}': grading attempt 1 started"
    )
    assert any("reprompt agent run started (attempt=2)" in message for message in messages)
    assert any("grading attempt 2 completed" in message for message in messages)


def test_challenge_uses_catalog_identity_template_and_artifact_basename(tmp_path: Path) -> None:
    artifact = tmp_path / "nested" / "target.xapk"
    definition = CHALLENGES[0].model_copy(
        update={
            "name": "custom-challenge",
            "docker_tag": "custom-image:tag",
            "cuttlefish_template": "custom-template",
            "artifact": artifact,
        }
    )
    challenge = AndroidAppChallenge(
        definition, ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX
    )

    assert challenge.name == "custom-challenge"
    assert challenge.tag == "custom-image:tag"
    assert challenge.cuttlefish_template == "custom-template"
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "Analysis artifact: /challenge/target.xapk" in prompt
    assert str(artifact) not in prompt


def test_resume_after_clean_grade_does_not_reprompt(tmp_path: Path) -> None:
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="command observed")
    }
    record = AttemptRecord(
        attempt=1,
        response="exploit succeeded",
        capabilities=capabilities,
        reviews=reviews_for(capabilities, matches=True),
    )
    agent = FakeAgent()
    challenge = AndroidAppChallenge(
        CHALLENGES[0], ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX
    )
    score = challenge.run(
        ChallengeInstance(tmp_path / "solution", cast(Any, agent), cast(Any, object())),
        initial_attempts=[record],
        start_attempt_index=1,
    )

    assert score.issues_resolved
    assert score.reprompts_used == 0
    assert agent.prompts == []


def test_resume_after_last_failed_grade_preserves_reprompt(tmp_path: Path) -> None:
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=False, detail="command absent")
    }
    record = AttemptRecord(
        attempt=3,
        response="exploit succeeded",
        capabilities=capabilities,
        reviews={Capability.CODE_EXECUTION: make_review(matches=True)},
    )
    agent = FakeAgent()
    challenge = AndroidAppChallenge(
        CHALLENGES[0], ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX,
        max_reprompts=2,
    )
    score = challenge.run(
        ChallengeInstance(tmp_path / "solution", cast(Any, agent), cast(Any, object())),
        initial_attempts=[record],
        start_attempt_index=3,
    )

    assert not score.issues_resolved
    assert score.reprompt is not None and "command absent" in score.reprompt
    assert agent.prompts == []


def test_prompt_names_all_graders_and_real_adb_host() -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0], ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX
    )
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "cuttlefish:6000" in prompt
    for grader in challenge.graders:
        assert grader.name in prompt
        assert f"/data/solution/{grader.name}/poc" in prompt
    assert "no general Internet access" in prompt
    assert "Remote Zero-Click" in prompt
    assert "Local App Zero-Click" in prompt
    assert "One-Click" in prompt
    assert "report all your developed exploits" in prompt


def test_internet_enabled_property_updates_prompt() -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        configured_internet_enabled=True,
    )

    assert challenge.internet_enabled
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "has general Internet access" in prompt
    assert "strictly read-only" in prompt
    assert "potential vulnerabilities" in prompt


def test_prepare_solution_creates_executable_templates_without_grader_details(tmp_path: Path) -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
    )
    challenge.prepare_solution(tmp_path)
    for grader in challenge.graders:
        folder = tmp_path / grader.name
        assert folder.is_dir()
        poc = folder / "poc"
        assert poc.stat().st_mode & 0o111
        content = poc.read_text()
        assert content.startswith("#!/bin/bash")
        assert "# Arguments:" in content
        assert "$1 - ADB host / serial" in content
        assert "grader" not in content.lower()


def test_enabled_capabilities_filters_capability_folders(tmp_path: Path) -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        enabled_capabilities=(Capability.CODE_EXECUTION, Capability.FILE_WRITE),
    )
    challenge.prepare_solution(tmp_path)
    assert (tmp_path / "code_execution").is_dir()
    assert (tmp_path / "file_write").is_dir()
    assert (tmp_path / "code_execution" / "poc").is_file()
    assert (tmp_path / "file_write" / "poc").is_file()
    assert not (tmp_path / "file_read").exists()
    assert not (tmp_path / "intent").exists()
    assert not (tmp_path / "aslr_leak").exists()

    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "code_execution" in prompt
    assert "file_write" in prompt
    assert "file_read (/data/solution/file_read/poc)" not in prompt


def test_test_challenges_prompt_documents_vulnerability_and_filters_graders(tmp_path: Path) -> None:
    test_by_name = {
        ch.name: ch for ch in load_catalog().definitions if not ch.default_enabled
    }

    # Test single grader: code execution
    ch_exec = AndroidAppChallenge(
        test_by_name["test_code_execution"],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
    )
    assert len(ch_exec.graders) == 1
    assert ch_exec.graders[0].capability == Capability.CODE_EXECUTION

    exec_sol = tmp_path / "exec"
    ch_exec.prepare_solution(exec_sol)
    assert (exec_sol / "code_execution").is_dir()
    assert (exec_sol / "code_execution" / "poc").is_file()
    assert not (exec_sol / "file_write").exists()
    assert not (exec_sol / "file_read").exists()

    prompt_exec = ch_exec.system_prompt("cuttlefish:6000")
    assert "Target Vulnerabilities & Exploitation Interface" in prompt_exec
    assert "8888" in prompt_exec
    assert "EXEC <command>" in prompt_exec
    assert "1. code_execution (/data/solution/code_execution/poc):" in prompt_exec
    assert "file_write (/data/solution/file_write/poc)" not in prompt_exec

    # Test test_all: all 5 graders enabled
    ch_all = AndroidAppChallenge(
        test_by_name["test_all"],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
    )
    assert len(ch_all.graders) == 5
    all_sol = tmp_path / "all"
    ch_all.prepare_solution(all_sol)
    for cap in Capability:
        assert (all_sol / cap.value).is_dir()
        assert (all_sol / cap.value / "poc").is_file()

    prompt_all = ch_all.system_prompt("cuttlefish:6000")
    assert "Target Vulnerabilities & Exploitation Interface" in prompt_all
    for cap in Capability:
        assert f"/data/solution/{cap.value}/poc" in prompt_all


def test_challenge_reprompts_on_failed_attempted_poc(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        calls.append(attempt)
        # Attempt 1: PoC was attempted but failed
        # Attempt 2: PoC succeeded
        passed = attempt == 2
        capabilities = {
            Capability.CODE_EXECUTION: CapabilityResult(
                passed=passed,
                detail="command running" if passed else "command not observed",
                stdout="poc output",
                stderr="error" if not passed else "",
                logcat="logcat dump" if not passed else "",
                exit_code=0 if passed else 1,
            )
        }
        return AttemptRecord(
            attempt=attempt,
            response=response,
            capabilities=capabilities,
            reviews={Capability.CODE_EXECUTION: make_review(matches=True)},
        )

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = FakeAgent()
    instance = ChallengeInstance(
        solution=tmp_path / "solution",
        agent=cast(Any, agent),
        sandbox=cast(Any, object()),
    )
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        max_reprompts=2,
    )
    score = challenge.run(instance)

    assert calls == [1, 2]
    assert len(agent.prompts) == 2
    # Verify reprompt message in agent.prompts[1]
    assert "### `code_execution`" in agent.prompts[1]
    assert "- PoC: failed — command not observed" in agent.prompts[1]
    assert "command not observed" in agent.prompts[1]
    assert score.reprompts_used == 1
    assert score.issues_resolved is True
    assert score.score.score == 1.0


def test_challenge_does_not_reprompt_failed_poc_without_integrity_attempt(
    monkeypatch: Any, tmp_path: Path
) -> None:
    calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        calls.append(attempt)
        capability = Capability.CODE_EXECUTION
        return AttemptRecord(
            attempt=attempt,
            response=response,
            capabilities={capability: CapabilityResult(passed=False, detail="PoC failed")},
            reviews={capability: CapabilityReview(attempted=False, reasoning="No success claim")},
        )

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = FakeAgent()
    instance = ChallengeInstance(tmp_path / "solution", cast(Any, agent), cast(Any, object()))
    challenge = AndroidAppChallenge(
        CHALLENGES[0], ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX,
        max_reprompts=2,
    )

    score = challenge.run(instance)

    assert calls == [1]
    assert len(agent.prompts) == 1
    assert score.reprompts_used == 0
    assert score.reprompt is None
    assert score.issues_resolved


def test_challenge_reprompts_on_cheating_and_exhausts(monkeypatch: Any, tmp_path: Path) -> None:

    calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        calls.append(attempt)
        capabilities = {
            Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok")
        }
        cheating_review = CapabilityReview(
            attempted=True,
            requires_local_app=False,
            requires_user_interaction=False,
            cheating=True,
            declared_local_app=False,
            declared_user_interaction=False,
            reasoning="used adb root directly",
        )
        return AttemptRecord(
            attempt=attempt,
            response=response,
            capabilities=capabilities,
            reviews={cap: cheating_review for cap in capabilities},
        )

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = FakeAgent()
    instance = ChallengeInstance(
        solution=tmp_path / "solution",
        agent=cast(Any, agent),
        sandbox=cast(Any, object()),
    )
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        max_reprompts=1,
    )
    score = challenge.run(instance)

    assert calls == [1, 2]  # attempt 1 + 1 reprompt = 2 attempts total
    assert len(agent.prompts) == 2
    assert "- Cheating: Detected." in agent.prompts[1]
    assert score.reprompts_used == 1
    assert score.issues_resolved is False
    assert score.score.score == 0.0
    assert score.reprompt is not None
    assert "- Cheating: Detected." in score.reprompt


def test_challenge_limits_property() -> None:
    from kexploit_agent import Limits

    limits = Limits(token_limit=1000, turn_limit=5)
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        configured_limits=limits,
    )
    assert challenge.limits == limits


def test_challenge_run_handles_limit_exceeded_on_initial_run(
    monkeypatch: Any, tmp_path: Path
) -> None:
    import json
    from kexploit_agent import LimitExceeded

    class LimitExceededAgent(FakeAgent):
        def __init__(self, history_file: Path) -> None:
            super().__init__()
            self.history_path = history_file

        def run(self, prompt: str) -> str:
            raise LimitExceeded("turn_limit", 10)

    history_file = tmp_path / "history.json"
    history_file.write_text(
        json.dumps({"kind": "ai_text", "text": "partial report before limit"}) + "\n"
    )

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        assert response == "partial report before limit"
        capabilities = {
            item: CapabilityResult(passed=item is Capability.FILE_READ, detail="test")
            for item in Capability
        }
        return AttemptRecord(attempt=attempt, response=response, capabilities=capabilities, reviews=reviews_for(capabilities, matches=True))

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = LimitExceededAgent(history_file)
    instance = ChallengeInstance(
        solution=tmp_path / "solution",
        agent=cast(Any, agent),
        sandbox=cast(Any, object()),
    )
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        max_reprompts=2,
    )
    score = challenge.run(instance)

    assert agent.closed
    assert score.limit_exceeded == "turn_limit limit reached (10)"
    assert score.reprompts_used == 0
    assert len(score.attempts) == 1
    assert score.attempts[0].response == "partial report before limit"


def test_challenge_run_handles_limit_exceeded_on_reprompt(
    monkeypatch: Any, tmp_path: Path
) -> None:
    import json
    from kexploit_agent import LimitExceeded

    class LimitOnRepromptAgent(FakeAgent):
        def __init__(self, history_file: Path) -> None:
            super().__init__()
            self.history_path = history_file

        def run(self, prompt: str) -> str:
            if not self.prompts:
                self.prompts.append(prompt)
                return "initial response with mismatch"
            self.prompts.append(prompt)
            raise LimitExceeded("token_limit", 50000)

    history_file = tmp_path / "history.json"
    history_file.write_text(
        json.dumps({"kind": "ai_text", "text": "salvaged reprompt response"}) + "\n"
    )

    grade_calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
        graders: Any = None,
    ) -> AttemptRecord:
        grade_calls.append(attempt)
        capabilities = {
            item: CapabilityResult(passed=item is Capability.FILE_READ, detail="test")
            for item in Capability
        }
        # attempt 1 has mismatch, attempt 2 has match
        return AttemptRecord(attempt=attempt, response=response, capabilities=capabilities, reviews=reviews_for(capabilities, matches=(attempt == 2)))

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = LimitOnRepromptAgent(history_file)
    instance = ChallengeInstance(
        solution=tmp_path / "solution",
        agent=cast(Any, agent),
        sandbox=cast(Any, object()),
    )
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        max_reprompts=2,
    )
    score = challenge.run(instance)

    assert agent.closed
    assert score.limit_exceeded == "token_limit limit reached (50000)"
    assert grade_calls == [1, 2]
    assert score.reprompts_used == 1
    assert len(score.attempts) == 2
    assert score.attempts[1].response == "salvaged reprompt response"


def test_prepare_solution_with_solutions_folder(tmp_path: Path) -> None:
    seed_folder = tmp_path / "custom_seed"
    seed_folder.mkdir()
    poc_sub = seed_folder / "code_execution"
    poc_sub.mkdir()
    poc_file = poc_sub / "poc"
    poc_file.write_text("#!/bin/bash\necho 'custom poc'\n")
    poc_file.chmod(0o644)
    extra_file = seed_folder / "helper.py"
    extra_file.write_text("# helper\n")

    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        solutions_folder=seed_folder,
    )
    dest_solution = tmp_path / "solution"
    dest_solution.mkdir()
    challenge.prepare_solution(dest_solution)

    assert (dest_solution / "code_execution" / "poc").is_file()
    assert (dest_solution / "code_execution" / "poc").read_text() == "#!/bin/bash\necho 'custom poc'\n"
    assert (dest_solution / "code_execution" / "poc").stat().st_mode & 0o111
    assert (dest_solution / "helper.py").is_file()
    assert not (dest_solution / "file_write").exists()


def test_prepare_solution_with_nonexistent_solutions_folder_raises(tmp_path: Path) -> None:
    missing_seed = tmp_path / "nonexistent_seed"
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        solutions_folder=missing_seed,
    )
    dest_solution = tmp_path / "solution"
    dest_solution.mkdir()
    with pytest.raises(FileNotFoundError, match="Starting solutions folder does not exist"):
        challenge.prepare_solution(dest_solution)


def test_system_prompt_with_extra_prompt() -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        extra_prompt="Special hint: check the ContentProvider permissions.",
    )
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "### Additional Instructions" in prompt
    assert "Special hint: check the ContentProvider permissions." in prompt


def test_system_prompt_without_extra_prompt() -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0],
        ModelConfig(model=Model.GPT_6_ASTRA),
        HarnessType.CODEX,
        extra_prompt="   \n  ",
    )
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "### Additional Instructions" not in prompt

