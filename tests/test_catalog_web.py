from pathlib import Path

import pytest
import tomli_w

from android_bench.catalog import ChallengeDefinition
from android_bench.models import Capability
from android_bench.web.service import load_run_detail


@pytest.mark.parametrize("explicit_selection", [False, True])
def test_web_uses_snapshot_for_private_pending_challenge(
    tmp_path: Path, explicit_selection: bool
) -> None:
    run = tmp_path / "private_run"
    snapshot = run / "catalog"
    snapshot.mkdir(parents=True)
    config = 'name = "private run"\n'
    if explicit_selection:
        config += 'challenges = ["private_app"]\n'
    (run / "challenge.toml").write_text(config)
    definition = ChallengeDefinition(
        name="private_app",
        artifact=tmp_path / "missing-private.apk",
        package="com.example.private",
        enabled_capabilities=(Capability.FILE_READ,),
        cuttlefish_template="private_template",
    )
    (snapshot / "private_app.toml").write_text(
        tomli_w.dumps(definition.model_dump(mode="json", exclude_none=True))
    )

    detail = load_run_detail(tmp_path, "private_run")

    assert len(detail.challenges) == 1
    challenge = detail.challenges[0]
    assert challenge.name == "private_app"
    assert challenge.package == "com.example.private"
    assert challenge.enabled_capabilities == ["file_read"]
    assert challenge.status == "pending"
