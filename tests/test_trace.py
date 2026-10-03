from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from android_bench.trace import (
    TranscriptMetadata,
    TranscriptParser,
    extract_final_response,
)


def test_imports() -> None:
    assert TranscriptParser is not None
    assert TranscriptMetadata is not None
    assert callable(extract_final_response)


def test_transcript_parser_from_agent(tmp_path: Path) -> None:
    path = tmp_path / "agent.json"
    path.write_text('{"event": "session_info", "session_id": "sess-agent-123"}\n')

    agent = MagicMock()
    agent.history_path = str(path)

    parser = TranscriptParser.from_agent(agent)
    assert parser is not None
    assert parser.get_session_id() == "sess-agent-123"

    agent_none = MagicMock()
    agent_none.history_path = None
    assert TranscriptParser.from_agent(agent_none) is None

    agent_missing = MagicMock()
    agent_missing.history_path = str(tmp_path / "does_not_exist.json")
    assert TranscriptParser.from_agent(agent_missing) is None


def test_transcript_parser_metadata(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps({
            "event": "session_end",
            "session_id": "sess-meta-1",
            "cost_usd": 0.0543,
            "token_usage": {"input": 1200, "output": 350},
        }) + "\n"
    )

    parser = TranscriptParser.from_file(path)
    meta = parser.get_metadata()
    assert meta.session_id == "sess-meta-1"
    assert meta.cost_usd == pytest.approx(0.0543)
    assert meta.token_usage is not None
    assert meta.token_usage.input_tokens == 1200
    assert meta.token_usage.output_tokens == 350


def test_extract_final_response_json_array(tmp_path: Path) -> None:
    path = tmp_path / "array_trace.json"
    events = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": [{"type": "text", "text": "final array response"}]},
    ]
    path.write_text(json.dumps(events))

    parser = TranscriptParser.from_file(path)
    assert parser.get_final_response() == "final array response"
    assert extract_final_response(path) == "final array response"


def test_count_agent_runs(tmp_path: Path) -> None:
    path = tmp_path / "runs.json"
    lines = [
        json.dumps({"event": "session_start"}),
        json.dumps({"event": "session_end"}),
        json.dumps({"event": "session_start"}),
        json.dumps({"event": "session_end"}),
    ]
    path.write_text("\n".join(lines) + "\n")

    parser = TranscriptParser.from_file(path)
    assert parser.count_agent_runs() == 2
