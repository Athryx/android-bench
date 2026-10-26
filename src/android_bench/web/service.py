from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tomllib
from typing import Any

from android_bench.catalog import load_catalog
from android_bench.models import CAPABILITY_WEIGHT, Capability
from android_bench.trace import TranscriptParser
from android_bench.web.models import (
    AttemptDetail,
    CapabilityDetail,
    ChallengeDetail,
    RunConfig,
    RunDetail,
    TreeNode,
    TreeResponse,
)

logger = logging.getLogger(__name__)


def get_kagent_web_host() -> str:
    """Get the normalized base URL for the kexploit agent web viewer."""
    host = os.environ.get("KAGENT_WEB_HOST", "http://localhost:8000").strip()
    if not host:
        host = "http://localhost:8000"
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return host.rstrip("/")


def build_trace_url(session_id: str | None) -> str | None:
    """Build a direct trace link to the kexploit agent web viewer."""
    if not session_id or not session_id.strip():
        return None
    return f"{get_kagent_web_host()}/sessions/{session_id.strip()}"

def extract_challenge_name(val: Any) -> str:
    """Safely extract a clean challenge name string from a string or challenge config dict."""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        name = val.get("name") or val.get("challenge")
        if isinstance(name, str):
            return name.strip()
    return ""


def is_run_dir(path: Path) -> bool:
    """Check if a directory contains a benchmark run."""
    if not path.is_dir():
        return False
    if (path / "challenge.toml").is_file() or (path / "challenge.json").is_file():
        return True
    results_toml = path / "results.toml"
    if results_toml.is_file():
        try:
            content = results_toml.read_text(encoding="utf-8")
            if "[results." in content or "total_runtime" in content:
                return True
        except Exception:
            pass
    return False


def get_run_timestamp(run_dir: Path) -> tuple[str, float]:
    """Extract start timestamp and human-formatted start time for a run."""
    # Check challenge.toml mtime first
    candidate_ts: float | None = None
    challenge_file = run_dir / "challenge.toml"
    if not challenge_file.is_file():
        challenge_file = run_dir / "challenge.json"

    if challenge_file.is_file():
        try:
            candidate_ts = challenge_file.stat().st_mtime
        except OSError:
            pass

    # Check transcript events for first timestamp
    if candidate_ts is None:
        for trans_file in sorted(run_dir.glob("*_transcript.json*")):
            try:
                for ev in TranscriptParser.from_file(trans_file).iter_events():
                    if isinstance(ev, dict) and "timestamp" in ev:
                        candidate_ts = float(ev["timestamp"])
                        break
                if candidate_ts is not None:
                    break
            except Exception:
                continue

    if candidate_ts is None:
        results_file = run_dir / "results.toml"
        if results_file.is_file():
            try:
                candidate_ts = results_file.stat().st_mtime
            except OSError:
                pass

    if candidate_ts is None:
        try:
            candidate_ts = run_dir.stat().st_mtime
        except OSError:
            candidate_ts = 0.0

    dt = datetime.fromtimestamp(candidate_ts, tz=timezone.utc).astimezone()
    formatted = dt.strftime("%b %d, %Y, %H:%M")
    return formatted, candidate_ts


def _read_toml_or_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".toml":
            return tomllib.loads(content)
        return json.loads(content)
    except Exception:
        return None


def get_run_metadata(run_dir: Path) -> tuple[str, str, float | None, str]:
    """Return (folder_name, challenge_name, score, status)."""
    folder_name = run_dir.name
    challenge_name = ""
    score: float | None = None
    status = "completed"

    cfg = _read_toml_or_json(run_dir / "challenge.toml")
    if not cfg:
        cfg = _read_toml_or_json(run_dir / "challenge.json")
    if cfg:
        if isinstance(cfg.get("name"), str):
            challenge_name = cfg["name"]
        elif isinstance(cfg.get("challenges"), list) and len(cfg["challenges"]) == 1:
            challenge_name = extract_challenge_name(cfg["challenges"][0])

    res = _read_toml_or_json(run_dir / "results.toml")
    if not res:
        res = _read_toml_or_json(run_dir / "results.json")
    if res:
        if "score" in res and isinstance(res["score"], (int, float)):
            score = float(res["score"])
        elif "overall_score" in res and isinstance(res["overall_score"], (int, float)):
            score = float(res["overall_score"])

        # Check status across challenge results
        results_dict = res.get("results")
        if isinstance(results_dict, dict):
            statuses = [
                v.get("status")
                for v in results_dict.values()
                if isinstance(v, dict) and "status" in v
            ]
            if any(s == "running" for s in statuses):
                status = "running"
            elif any(s == "failed" for s in statuses) and not any(s == "completed" for s in statuses):
                status = "failed"
    else:
        status = "running" if (run_dir / "challenge.toml").is_file() else "unknown"

    return folder_name, challenge_name, score, status


def build_run_tree_node(run_dir: Path, root_dir: Path) -> TreeNode:
    """Build a TreeNode for a benchmark run directory."""
    folder_name, challenge_name, score, status = get_run_metadata(run_dir)
    started_at, started_ts = get_run_timestamp(run_dir)

    try:
        rel_path = str(run_dir.relative_to(root_dir))
    except ValueError:
        rel_path = run_dir.name

    if challenge_name and challenge_name != folder_name:
        display_name = f"{folder_name} ({challenge_name})"
    else:
        display_name = folder_name

    return TreeNode(
        type="run",
        name=folder_name,
        display_name=display_name,
        path=rel_path,
        full_path=str(run_dir.resolve()),
        started_at=started_at,
        started_timestamp=started_ts,
        score=score,
        status=status,
    )


def scan_results_tree(root_dir: Path) -> list[TreeNode]:
    """Scan root_dir recursively to build a tree of folders and runs."""
    resolved_root = root_dir.resolve()
    if not resolved_root.is_dir():
        return []

    # If the root itself is a run directory
    if is_run_dir(resolved_root):
        return [build_run_tree_node(resolved_root, resolved_root)]

    def _scan_dir(current_dir: Path) -> list[TreeNode]:
        nodes: list[TreeNode] = []
        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return []

        for entry in entries:
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            if is_run_dir(entry):
                nodes.append(build_run_tree_node(entry, resolved_root))
            else:
                child_nodes = _scan_dir(entry)
                if child_nodes:
                    try:
                        rel_path = str(entry.relative_to(resolved_root))
                    except ValueError:
                        rel_path = entry.name
                    nodes.append(
                        TreeNode(
                            type="folder",
                            name=entry.name,
                            display_name=entry.name,
                            path=rel_path,
                            full_path=str(entry.resolve()),
                            children=child_nodes,
                        )
                    )

        # Sort: folders first, then runs by started_timestamp descending
        folders = [n for n in nodes if n.type == "folder"]
        runs = [n for n in nodes if n.type == "run"]
        runs.sort(key=lambda r: r.started_timestamp or 0.0, reverse=True)
        return folders + runs

    return _scan_dir(resolved_root)


def load_run_detail(root_dir: Path, rel_path: str) -> RunDetail:
    """Load complete details for a specific benchmark run."""
    resolved_root = root_dir.resolve()
    if rel_path == "." or not rel_path.strip():
        run_dir = resolved_root
    else:
        run_dir = (resolved_root / rel_path).resolve()

    # Safety check: path must be inside root_dir or equal to root_dir
    try:
        run_dir.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path '{rel_path}' is outside root results directory") from exc

    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {rel_path}")

    folder_name, challenge_name, run_score, status = get_run_metadata(run_dir)
    started_at, started_ts = get_run_timestamp(run_dir)

    # Read NOTES.md if present
    notes_content: str | None = None
    notes_file = run_dir / "NOTES.md"
    if notes_file.is_file():
        try:
            notes_content = notes_file.read_text(encoding="utf-8")
        except OSError:
            pass

    # Read config
    raw_toml = ""
    config_dict = _read_toml_or_json(run_dir / "challenge.toml")
    if (run_dir / "challenge.toml").is_file():
        try:
            raw_toml = (run_dir / "challenge.toml").read_text(encoding="utf-8")
        except OSError:
            pass
    elif not config_dict:
        config_dict = _read_toml_or_json(run_dir / "challenge.json")

    run_config = RunConfig(raw_toml=raw_toml)
    if config_dict:
        run_config.name = str(config_dict.get("name", ""))
        run_config.harness = str(config_dict.get("harness", ""))
        run_config.num_instances = config_dict.get("num_instances")
        run_config.internet_enabled = config_dict.get("internet_enabled")
        run_config.summarize = config_dict.get("summarize")
        run_config.max_reprompts = config_dict.get("max_reprompts")
        if isinstance(config_dict.get("model_config"), dict):
            mc = config_dict["model_config"]
            run_config.model = str(mc.get("model", ""))
            run_config.model_effort = str(mc.get("model_effort", ""))
        if isinstance(config_dict.get("limits"), dict):
            run_config.time_limit = config_dict["limits"].get("time_limit")

    # Read benchmark results
    results_dict = _read_toml_or_json(run_dir / "results.toml")
    if not results_dict:
        results_dict = _read_toml_or_json(run_dir / "results.json")

    total_runtime = 0.0
    overall_score = run_score or 0.0
    if results_dict:
        total_runtime = float(results_dict.get("total_runtime", 0.0))
        if "score" in results_dict and isinstance(results_dict["score"], (int, float)):
            overall_score = float(results_dict["score"])

    # Map challenge configs by clean challenge name
    challenge_configs_by_name: dict[str, dict[str, Any]] = {}
    if config_dict and isinstance(config_dict.get("challenges"), list):
        for item in config_dict["challenges"]:
            c_name = extract_challenge_name(item)
            if c_name:
                challenge_configs_by_name[c_name] = item if isinstance(item, dict) else {"name": c_name}

    catalog_dir = run_dir / "catalog"
    try:
        catalog = load_catalog(catalog_dir if catalog_dir.is_dir() else None)
        definitions_by_name = catalog.by_name
        if catalog_dir.is_dir() and not challenge_configs_by_name:
            challenge_configs_by_name = {
                definition.name: {"name": definition.name}
                for definition in catalog.definitions
            }
    except (OSError, ValueError):
        logger.warning("Could not load challenge catalog for %s", run_dir, exc_info=True)
        definitions_by_name = {}

    # Build challenges list
    challenges_map: dict[str, dict[str, Any]] = {}
    if results_dict and isinstance(results_dict.get("results"), dict):
        for ch_key, ch_data in results_dict["results"].items():
            if isinstance(ch_data, dict):
                clean_name = extract_challenge_name(ch_data.get("challenge")) or extract_challenge_name(ch_key)
                if clean_name:
                    challenges_map[clean_name] = ch_data

    # Also inspect challenge subdirectories for any additional or more detailed data
    for sub in run_dir.iterdir():
        if sub.is_dir() and not sub.name.startswith("."):
            sub_res_file = sub / "results.toml"
            if not sub_res_file.is_file():
                sub_res_file = sub / "results.json"
            if sub_res_file.is_file():
                sub_data = _read_toml_or_json(sub_res_file)
                if sub_data and isinstance(sub_data, dict):
                    clean_name = extract_challenge_name(sub_data.get("challenge")) or extract_challenge_name(sub.name)
                    if clean_name:
                        if clean_name in challenges_map:
                            # Merge detailed sub_data (e.g. attempts) if missing
                            if "attempts" not in challenges_map[clean_name] and "attempts" in sub_data:
                                challenges_map[clean_name]["attempts"] = sub_data["attempts"]
                        else:
                            challenges_map[clean_name] = sub_data

    # Also check if challenge_test.toml or challenge.toml lists challenges that haven't started
    for ch_name_key in challenge_configs_by_name:
        if ch_name_key not in challenges_map:
            challenges_map[ch_name_key] = {
                "challenge": ch_name_key,
                "status": "pending",
                "score": 0.0,
                "runtime": 0.0,
            }

    challenge_details: list[ChallengeDetail] = []
    for ch_name, data in sorted(challenges_map.items()):
        raw_score = data.get("score", 0.0)
        ch_score = float(raw_score.get("score", 0.0) if isinstance(raw_score, dict) else (raw_score or 0.0))
        ch_status = str(data.get("status", "completed"))
        session_id = data.get("session_id")

        # Locate transcript file if present to resolve session_id, cost, token usage
        ch_dir = run_dir / ch_name
        transcript_file: Path | None = None
        for cand in [
            run_dir / f"{ch_name}_transcript.json",
            run_dir / f"{ch_name}_transcript.jsons",
            ch_dir / f"{ch_name}_transcript.json",
            ch_dir / f"{ch_name}_transcript.jsons",
            ch_dir / "transcript.json",
            ch_dir / "transcript.jsons",
        ]:
            if cand.is_file():
                transcript_file = cand
                break

        trans_meta = None
        if transcript_file is not None:
            try:
                trans_meta = TranscriptParser.from_file(transcript_file).get_metadata()
            except Exception:
                pass

        if not session_id and trans_meta is not None:
            session_id = trans_meta.session_id

        trace_url = build_trace_url(session_id)

        cost_usd: float | None = None
        if "cost_usd" in data and isinstance(data["cost_usd"], (int, float)):
            cost_usd = float(data["cost_usd"])
        elif "cost" in data and isinstance(data["cost"], (int, float)):
            cost_usd = float(data["cost"])
        elif trans_meta is not None:
            cost_usd = trans_meta.cost_usd

        token_usage: dict[str, Any] | None = None
        if isinstance(data.get("token_usage"), dict):
            token_usage = data["token_usage"]
        elif isinstance(data.get("tokens"), dict):
            token_usage = data["tokens"]
        elif trans_meta is not None and trans_meta.token_usage:
            if hasattr(trans_meta.token_usage, "model_dump"):
                token_usage = trans_meta.token_usage.model_dump()
            elif isinstance(trans_meta.token_usage, dict):
                token_usage = trans_meta.token_usage

        # Parse axes
        raw_axes = data.get("axes", {})
        axes_dict: dict[str, float] = {}
        if isinstance(raw_axes, dict):
            for ax_k, ax_v in raw_axes.items():
                if isinstance(ax_v, (int, float)):
                    axes_dict[str(ax_k)] = float(ax_v)

        # Parse attempts
        attempts_list: list[AttemptDetail] = []
        raw_attempts = data.get("attempts", [])

        # If attempts are empty in results dict, check challenge directory grading/ folder
        if not raw_attempts:
            ch_dir = run_dir / ch_name
            grading_dir = ch_dir / "grading"
            if grading_dir.is_dir():
                for att_file in sorted(grading_dir.glob("attempt-*.toml")):
                    att_data = _read_toml_or_json(att_file)
                    if att_data:
                        raw_attempts.append(att_data)

        if isinstance(raw_attempts, list):
            for att in raw_attempts:
                if not isinstance(att, dict):
                    continue
                att_num = int(att.get("attempt", len(attempts_list) + 1))
                att_resp = str(att.get("response", ""))
                att_reprompt = att.get("reprompt")
                if att_reprompt is not None:
                    att_reprompt = str(att_reprompt)

                capabilities_dict: dict[str, CapabilityDetail] = {}
                raw_caps = att.get("capabilities", {})
                raw_reviews = att.get("reviews", {})

                # Merge capabilities and reviews
                all_cap_keys = set()
                if isinstance(raw_caps, dict):
                    all_cap_keys.update(raw_caps.keys())
                if isinstance(raw_reviews, dict):
                    all_cap_keys.update(raw_reviews.keys())

                for cap_name in sorted(all_cap_keys):
                    cap_res = raw_caps.get(cap_name, {}) if isinstance(raw_caps, dict) else {}
                    cap_rev = raw_reviews.get(cap_name, {}) if isinstance(raw_reviews, dict) else {}

                    weight = 0.0
                    try:
                        enum_cap = Capability(cap_name)
                        weight = CAPABILITY_WEIGHT.get(enum_cap, 0.0)
                    except ValueError:
                        pass

                    raw_attempted = cap_rev.get("attempted")
                    if raw_attempted is not None:
                        is_attempted = bool(raw_attempted)
                    else:
                        is_attempted = bool(cap_res.get("passed", False)) or bool(cap_res.get("stdout")) or bool(cap_res.get("stderr"))

                    cap_passed = bool(cap_res.get("passed", False)) and is_attempted
                    has_integrity = bool(
                        cap_rev.get("cheating") is True
                        or (is_attempted and cap_rev.get("declared_local_app") != cap_rev.get("requires_local_app"))
                        or (is_attempted and cap_rev.get("declared_user_interaction") != cap_rev.get("requires_user_interaction"))
                    )

                    cap_score = axes_dict.get(cap_name, weight if cap_passed and not has_integrity else 0.0)
                    if not is_attempted:
                        cap_score = 0.0

                    capabilities_dict[str(cap_name)] = CapabilityDetail(
                        name=str(cap_name),
                        passed=cap_passed,
                        detail=str(cap_res.get("detail", "")),
                        score=cap_score,
                        weight=weight,
                        stdout=str(cap_res.get("stdout", "")),
                        stderr=str(cap_res.get("stderr", "")),
                        logcat=str(cap_res.get("logcat", "")),
                        exit_code=cap_res.get("exit_code"),
                        attempted=is_attempted,
                        cheating=cap_rev.get("cheating"),
                        requires_local_app=cap_rev.get("requires_local_app"),
                        requires_user_interaction=cap_rev.get("requires_user_interaction"),
                        declared_local_app=cap_rev.get("declared_local_app"),
                        declared_user_interaction=cap_rev.get("declared_user_interaction"),
                        has_integrity_issue=has_integrity,
                        reasoning=str(cap_rev.get("reasoning", "")),
                    )

                attempts_list.append(
                    AttemptDetail(
                        attempt=att_num,
                        response=att_resp,
                        reprompt=att_reprompt,
                        capabilities=capabilities_dict,
                    )
                )

        # Determine configured / enabled capabilities for this challenge
        configured_caps: list[str] = []
        ch_cfg = challenge_configs_by_name.get(ch_name)
        ch_def = definitions_by_name.get(ch_name)

        if "enabled_capabilities" in data and isinstance(data["enabled_capabilities"], list):
            configured_caps = [str(c) for c in data["enabled_capabilities"]]
        elif ch_cfg and "capabilities" in ch_cfg and isinstance(ch_cfg["capabilities"], list):
            configured_caps = [str(c) for c in ch_cfg["capabilities"]]
        elif config_dict and "capabilities" in config_dict and isinstance(config_dict["capabilities"], list):
            configured_caps = [str(c) for c in config_dict["capabilities"]]
        elif ch_def is not None:
            if ch_def.enabled_capabilities is not None:
                configured_caps = [c.value for c in ch_def.enabled_capabilities]
            else:
                configured_caps = [c.value for c in Capability]

        # Also include any capability that appears in axes or was graded in attempts
        all_caps_set = set(configured_caps)
        all_caps_set.update(axes_dict.keys())
        for att in attempts_list:
            all_caps_set.update(att.capabilities.keys())

        # Preserve canonical order: standard Capability order first, then any extra
        ordered_caps: list[str] = []
        for c in Capability:
            if c.value in all_caps_set:
                ordered_caps.append(c.value)
        for c in sorted(all_caps_set):
            if c not in ordered_caps:
                ordered_caps.append(c)

        pkg = str(data.get("package", "")).strip()
        if not pkg and ch_def is not None:
            pkg = ch_def.package

        challenge_details.append(
            ChallengeDetail(
                name=ch_name,
                package=pkg,
                status=ch_status,
                score=ch_score,
                runtime=float(data.get("runtime", 0.0)),
                session_id=str(session_id) if session_id else None,
                trace_url=trace_url,
                cost_usd=cost_usd,
                token_usage=token_usage,
                axes=axes_dict,
                enabled_capabilities=ordered_caps,
                attempts=attempts_list,
                limit_exceeded=data.get("limit_exceeded"),
                error=data.get("error"),
            )
        )

    run_cost: float | None = None
    if results_dict and "cost_usd" in results_dict and isinstance(results_dict["cost_usd"], (int, float)):
        run_cost = float(results_dict["cost_usd"])
    elif results_dict and "total_cost" in results_dict and isinstance(results_dict["total_cost"], (int, float)):
        run_cost = float(results_dict["total_cost"])
    else:
        ch_costs = [ch.cost_usd for ch in challenge_details if ch.cost_usd is not None]
        if ch_costs:
            run_cost = sum(ch_costs)

    run_tokens: dict[str, Any] | None = None
    if results_dict and isinstance(results_dict.get("token_usage"), dict):
        run_tokens = results_dict["token_usage"]
    else:
        merged_tokens: dict[str, int] = {}
        has_tokens = False
        for ch in challenge_details:
            if ch.token_usage:
                for k, v in ch.token_usage.items():
                    if isinstance(v, (int, float)):
                        merged_tokens[k] = merged_tokens.get(k, 0) + int(v)
                        has_tokens = True
        if has_tokens:
            run_tokens = merged_tokens

    if challenge_name and challenge_name != folder_name:
        display_name = f"{folder_name} ({challenge_name})"
    else:
        display_name = folder_name

    return RunDetail(
        path=rel_path,
        full_path=str(run_dir.resolve()),
        folder_name=folder_name,
        challenge_name=challenge_name,
        display_name=display_name,
        started_at=started_at,
        started_timestamp=started_ts,
        score=overall_score,
        total_runtime=total_runtime,
        cost_usd=run_cost,
        token_usage=run_tokens,
        status=status,
        notes=notes_content,
        config=run_config,
        challenges=challenge_details,
    )
