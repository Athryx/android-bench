from pathlib import Path
from typing import Any, cast

from kbench import ChallengeInstance
from kexploit_agent import HarnessType, Model, ModelConfig

from android_bench.catalog import CHALLENGES
from android_bench.challenge import AndroidAppChallenge
from android_bench.grader import AttemptGrade
from android_bench.models import Capability, CapabilityResult, DeliveryClass, ExploitAssessment


class FakeAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.closed = False

    def run(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"response {len(self.prompts)}"

    def close(self) -> None:
        self.closed = True


def assessment(matches: bool) -> ExploitAssessment:
    return ExploitAssessment(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False if matches else True,
        declared_user_interaction=False,
        delivery_class=DeliveryClass.REMOTE_ZERO_CLICK,
        reason="test",
    )


def test_mismatch_reprompts_and_regrades_fresh(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[int] = []

    def fake_grade_attempt(
        instance: ChallengeInstance,
        definition: Any,
        response: str,
        attempt: int,
    ) -> AttemptGrade:
        calls.append(attempt)
        capabilities = {
            item: CapabilityResult(passed=item is Capability.FILE_READ, detail="test")
            for item in Capability
        }
        return AttemptGrade(capabilities, assessment(matches=attempt == 2))

    monkeypatch.setattr("android_bench.challenge.grade_attempt", fake_grade_attempt)
    agent = FakeAgent()
    instance = ChallengeInstance(
        solution=tmp_path,
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
    assert agent.closed
    assert score.reprompts_used == 1
    assert score.disclosure_resolved
    assert (tmp_path / "grading" / "attempt-1.json").is_file()
    assert (tmp_path / "grading" / "attempt-2.json").is_file()


def test_prompt_names_all_graders_and_real_adb_host() -> None:
    challenge = AndroidAppChallenge(
        CHALLENGES[0], ModelConfig(model=Model.GPT_6_ASTRA), HarnessType.CODEX
    )
    prompt = challenge.system_prompt("cuttlefish:6000")
    assert "cuttlefish:6000" in prompt
    for capability in Capability:
        assert capability.value in prompt
