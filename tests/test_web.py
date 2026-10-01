from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from android_bench.web.models import TreeResponse, RunDetail
from android_bench.web.server import create_app
from android_bench.web.service import (
    build_trace_url,
    get_kagent_web_host,
    get_run_timestamp,
    is_run_dir,
    load_run_detail,
    scan_results_tree,
)


def test_get_kagent_web_host_default() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert get_kagent_web_host() == "http://localhost:8000"


def test_get_kagent_web_host_custom() -> None:
    with patch.dict(os.environ, {"KAGENT_WEB_HOST": "traces.local:9000/"}):
        assert get_kagent_web_host() == "http://traces.local:9000"

    with patch.dict(os.environ, {"KAGENT_WEB_HOST": "https://secure.traces.com/"}):
        assert get_kagent_web_host() == "https://secure.traces.com"


def test_build_trace_url() -> None:
    with patch.dict(os.environ, {"KAGENT_WEB_HOST": "http://192.168.1.50:8000"}):
        assert build_trace_url("session-1234") == "http://192.168.1.50:8000/sessions/session-1234"
        assert build_trace_url("") is None
        assert build_trace_url(None) is None


def test_is_run_dir(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert not is_run_dir(empty_dir)

    run_dir_with_challenge = tmp_path / "run_cfg"
    run_dir_with_challenge.mkdir()
    (run_dir_with_challenge / "challenge.toml").write_text('name = "test"\n')
    assert is_run_dir(run_dir_with_challenge)

    run_dir_with_benchmark_results = tmp_path / "run_res"
    run_dir_with_benchmark_results.mkdir()
    (run_dir_with_benchmark_results / "results.toml").write_text('score = 1.0\ntotal_runtime = 100.0\n[results.test]\nscore=1.0\n')
    assert is_run_dir(run_dir_with_benchmark_results)

    challenge_subfolder = tmp_path / "challenge_sub"
    challenge_subfolder.mkdir()
    (challenge_subfolder / "results.toml").write_text('challenge = "test"\nscore = 1.0\n')
    assert not is_run_dir(challenge_subfolder)


def test_scan_results_tree_nested(tmp_path: Path) -> None:
    # Structure:
    # tmp_path/
    #   group_a/
    #     run_1/ (challenge.toml name = "deepseek_eval")
    #   run_top/ (challenge.toml name = "run_top")
    group_a = tmp_path / "group_a"
    group_a.mkdir()

    run_1 = group_a / "run_1"
    run_1.mkdir()
    (run_1 / "challenge.toml").write_text('name = "deepseek_eval"\n')
    (run_1 / "results.toml").write_text('score = 0.8\ntotal_runtime = 45.0\n')

    run_top = tmp_path / "run_top"
    run_top.mkdir()
    (run_top / "challenge.toml").write_text('name = "top_run"\n')
    (run_top / "results.toml").write_text('score = 1.0\ntotal_runtime = 120.0\n')

    items = scan_results_tree(tmp_path)
    assert len(items) == 2

    # group_a is a folder node
    folder_node = next(i for i in items if i.type == "folder")
    assert folder_node.name == "group_a"
    assert len(folder_node.children) == 1
    assert folder_node.children[0].type == "run"
    assert folder_node.children[0].name == "run_1"
    assert folder_node.children[0].display_name == "run_1 (deepseek_eval)"
    assert folder_node.children[0].score == 0.8

    # run_top is a run node
    run_top_node = next(i for i in items if i.type == "run")
    assert run_top_node.name == "run_top"
    assert run_top_node.display_name == "run_top (top_run)"
    assert run_top_node.score == 1.0


def test_load_run_detail_with_notes_and_attempts(tmp_path: Path) -> None:
    run_dir = tmp_path / "my_run"
    run_dir.mkdir()
    (run_dir / "challenge.toml").write_text(
        """name = "cve_exp"
harness = "pi_plus"
num_instances = 3
internet_enabled = true
[model_config]
model = "claude-3-7-sonnet"
model_effort = "high"
[limits]
time_limit = 7200.0
"""
    )
    (run_dir / "NOTES.md").write_text("# Experiment Notes\nTested prompt v2.\n")
    (run_dir / "results.toml").write_text(
        """score = 1.0
total_runtime = 500.0
[results.cve_app]
challenge = "cve_app"
package = "com.test.cve"
status = "completed"
session_id = "test-session-uuid"
score = 1.0
runtime = 490.0
[results.cve_app.axes]
code_execution = 1.0
file_write = 0.3

[[results.cve_app.attempts]]
attempt = 1
response = "I exploited the target."
reprompt = "Fix the intent delivery."
[results.cve_app.attempts.capabilities.code_execution]
passed = true
detail = "UID matched"
stdout = "OK"
exit_code = 0
[results.cve_app.attempts.reviews.code_execution]
attempted = true
cheating = false
requires_local_app = false
requires_user_interaction = false
declared_local_app = false
declared_user_interaction = false
reasoning = "Clean network exploit."
"""
    )

    detail = load_run_detail(tmp_path, "my_run")
    assert detail.folder_name == "my_run"
    assert detail.challenge_name == "cve_exp"
    assert detail.display_name == "my_run (cve_exp)"
    assert detail.score == 1.0
    assert detail.total_runtime == 500.0
    assert detail.notes == "# Experiment Notes\nTested prompt v2.\n"
    assert detail.config.model == "claude-3-7-sonnet"
    assert detail.config.harness == "pi_plus"
    assert detail.config.time_limit == 7200.0

    assert len(detail.challenges) == 1
    ch = detail.challenges[0]
    assert ch.name == "cve_app"
    assert ch.session_id == "test-session-uuid"
    assert ch.trace_url == "http://localhost:8000/sessions/test-session-uuid"
    assert ch.score == 1.0
    assert ch.axes == {"code_execution": 1.0, "file_write": 0.3}

    assert len(ch.attempts) == 1
    att = ch.attempts[0]
    assert att.attempt == 1
    assert att.response == "I exploited the target."
    assert att.reprompt == "Fix the intent delivery."
    assert "code_execution" in att.capabilities
    cap = att.capabilities["code_execution"]
    assert cap.passed is True
    assert cap.stdout == "OK"
    assert cap.exit_code == 0
    assert cap.cheating is False
    assert cap.reasoning == "Clean network exploit."


def test_load_run_detail_path_traversal_prevention(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside root results directory"):
        load_run_detail(tmp_path, "../../etc/passwd")


def test_web_server_endpoints(tmp_path: Path) -> None:
    # Setup mock results directory
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    (run_dir / "challenge.toml").write_text('name = "run_alpha"\n')
    (run_dir / "results.toml").write_text('score = 1.0\ntotal_runtime = 50.0\n')

    app = create_app(tmp_path)
    client = TestClient(app)

    # GET / (HTML index)
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "android-bench" in res_index.text
    assert "<title>android-bench Results Viewer</title>" in res_index.text

    # GET /api/config
    res_cfg = client.get("/api/config")
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert cfg_data["results_dir"] == str(tmp_path.resolve())
    assert cfg_data["kagent_web_host"] == "http://localhost:8000"

    # GET /api/tree
    res_tree = client.get("/api/tree")
    assert res_tree.status_code == 200
    tree_data = res_tree.json()
    assert len(tree_data["items"]) == 1
    assert tree_data["items"][0]["name"] == "test_run"
    assert tree_data["items"][0]["display_name"] == "test_run (run_alpha)"

    # GET /api/runs/{run_path}
    res_run = client.get("/api/runs/test_run")
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["folder_name"] == "test_run"
    assert run_data["challenge_name"] == "run_alpha"
    assert run_data["score"] == 1.0

    # GET /api/runs/nonexistent -> 404
    res_404 = client.get("/api/runs/nonexistent")
    assert res_404.status_code == 404


def test_load_existing_results_test_directory() -> None:
    """Test loading the real results/results_test directory in the repository."""
    results_root = Path(__file__).parent.parent / "results"
    if (results_root / "results_test").is_dir():
        items = scan_results_tree(results_root)
        assert any(i.name == "results_test" for i in items)

        detail = load_run_detail(results_root, "results_test")
        assert detail.folder_name == "results_test"
        assert detail.challenge_name == "run1"
        assert detail.score == 1.0
        assert len(detail.challenges) >= 1
        ch = detail.challenges[0]
        assert ch.name == "test_all"
        assert ch.session_id == "e2eeb588-aa41-4e26-8440-93a0845c679b"
        assert ch.trace_url == "http://localhost:8000/sessions/e2eeb588-aa41-4e26-8440-93a0845c679b"
        assert len(ch.attempts) >= 1
