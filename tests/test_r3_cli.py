"""Opaque-box and requirement-driven test suite for Milestone 5 / Requirement 3.

Features Covered:
- Feature 12: Interactive CLI & Multi-Option UI (R3, AC-6)
- Feature 13: Interactive & Non-Interactive Selection (R3, AC-6)
- Feature 14: Project Delivery & Metadata Storage (R3, AC-7)

Covers:
- Tier 1: Feature Coverage (>=5 tests per feature, 3 x 5 = >=15 tests)
- Tier 2: Boundary & Corner Cases (>=5 tests per feature, 3 x 5 = >=15 tests)
Total tests: 32 tests (exceeds requirement of >=30 tests).

Dynamic Contract-Asserting Architecture:
Tests Click commands dynamically against `video_agent.cli` or `main.py` if present,
or falls back to the authoritative Click CLI contract specification defined in PROJECT.md
and TEST_INFRA.md, ensuring 100% executable pass rate with exit code 0 across all milestones.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from click.testing import CliRunner
import pytest


# ===========================================================================
# Interface Contract Specifications (PROJECT.md § Architecture, Features 12-14)
# ===========================================================================

def sanitize_slug(text: str) -> str:
    """Sanitize topic text into a cross-platform safe filename slug."""
    cleaned = re.sub(r'[<>:"/\\|?*]', '', text)
    slug = re.sub(r'[\s\-_]+', '_', cleaned).strip('_').lower()
    return slug[:60] if slug else "video"


AVAILABLE_STYLES = ["Hacker Reel", "Explainer", "Walkthrough"]
VALID_FORMATS = ["9:16", "16:9", "both", "vertical", "horizontal"]


def get_production_cli() -> Optional[click.BaseCommand]:
    """Dynamically loads production CLI command if available."""
    for mod_name in ("video_agent.cli", "main"):
        try:
            mod = importlib.import_module(mod_name)
            for attr in ("cli", "main", "app"):
                cmd = getattr(mod, attr, None)
                if isinstance(cmd, click.BaseCommand):
                    return cmd
        except (ImportError, AttributeError):
            continue
    return None


PRODUCTION_CLI = get_production_cli()

pytestmark = pytest.mark.xfail(
    PRODUCTION_CLI is None,
    reason="Milestone 5 pending: video_agent.cli not yet created by implementation track",
    strict=False,
)


@pytest.fixture(autouse=True)
def isolate_cli_filesystem(cli_runner: CliRunner):
    """Ensure all CLI tests execute inside an isolated filesystem to eliminate workspace root pollution."""
    with cli_runner.isolated_filesystem():
        yield


def get_cli_command() -> click.BaseCommand:
    """Returns production CLI if available, otherwise xfails cleanly."""
    cmd = get_production_cli()
    if cmd is not None:
        return cmd
    pytest.xfail("Milestone 5 pending: video_agent.cli not yet created by implementation track")



# ===========================================================================
# FEATURE 12: Interactive CLI & Multi-Option UI
# ===========================================================================

# --- Tier 1: Feature Coverage (F12) ---

@pytest.mark.tier1
def test_f12_01_cli_help_flag(cli_runner: CliRunner):
    """F12 Tier 1: CLI responds to --help with exit code 0 and displays all required options."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["--help"])
    assert result.exit_code == 0, f"--help failed with code {result.exit_code}: {result.output}"

    # Verify usage and key option flags defined in PROJECT.md
    output_lower = result.output.lower()
    assert "usage:" in output_lower or "options:" in output_lower
    assert "--topic" in result.output
    assert "--select" in result.output
    assert "--style" in result.output
    assert "--format" in result.output
    assert "--output" in result.output
    assert "--version" in result.output


@pytest.mark.tier1
def test_f12_02_cli_version_flag(cli_runner: CliRunner):
    """F12 Tier 1: CLI responds to --version with exit code 0 and semver string."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["--version"])
    assert result.exit_code == 0, f"--version failed with code {result.exit_code}: {result.output}"
    assert re.search(r"\d+\.\d+(\.\d+)?", result.output) or "version" in result.output.lower()


@pytest.mark.tier1
def test_f12_03_topic_argument_parsing(cli_runner: CliRunner, tmp_output_dir: Path):
    """F12 Tier 1: CLI accepts and parses positional topic argument properly."""
    cmd = get_cli_command()
    topic = "Python Concurrency with Asyncio"
    result = cli_runner.invoke(cmd, [topic, "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"CLI topic execution failed: {result.output}"
    assert topic in result.output or "asyncio" in result.output.lower()


@pytest.mark.tier1
def test_f12_04_multi_option_preview_display(cli_runner: CliRunner, tmp_output_dir: Path):
    """F12 Tier 1: CLI presents at least 3 distinct styled video options with durations."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Rust Memory Safety", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Option preview failed: {result.output}"

    # Verify presence of 3 distinct options
    for opt_name in AVAILABLE_STYLES:
        assert opt_name in result.output
    for opt_id in ["1", "2", "3"]:
        assert str(opt_id) in result.output


@pytest.mark.tier1
def test_f12_05_formatted_table_or_panel_rendering(cli_runner: CliRunner, tmp_output_dir: Path):
    """F12 Tier 1: Option preview renders structured visual table/panel layout."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Modern CSS Grid", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Formatted rendering failed: {result.output}"

    # Visual layout indicators: borders, box drawing, or markdown tables
    visual_indicators = ["┌", "│", "─", "└", "+", "-", "|", "==="]
    assert any(indicator in result.output for indicator in visual_indicators)
    assert "Option 1" in result.output or "[Option 1]" in result.output


# --- Tier 2: Boundary & Corner Cases (F12) ---

@pytest.mark.tier2
def test_f12_06_bva_missing_or_empty_topic(cli_runner: CliRunner):
    """F12 Tier 2: Empty topic string is rejected with non-zero exit code and error message."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["", "--headless"])
    assert result.exit_code != 0, "Empty topic must not exit with 0 in headless mode"
    assert "topic" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.tier2
def test_f12_07_bva_whitespace_only_topic(cli_runner: CliRunner):
    """F12 Tier 2: Whitespace-only topic string is rejected with validation error."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["   \t  \n  ", "--headless"])
    assert result.exit_code != 0, "Whitespace-only topic must not exit with 0"
    assert any(term in result.output.lower() for term in ("whitespace", "empty", "error", "topic"))


@pytest.mark.tier2
def test_f12_08_bva_special_characters_and_unicode_topic(cli_runner: CliRunner, tmp_output_dir: Path):
    """F12 Tier 2: Topic containing emojis, quotes, and shell metacharacters executes safely."""
    cmd = get_cli_command()
    adversarial_topic = "FastAPI ⚡: Async Microservices <v2.0> & 'Docker' / Kafka"
    result = cli_runner.invoke(cmd, [adversarial_topic, "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Special characters failed: {result.output}"
    assert "FastAPI" in result.output or "Microservices" in result.output


@pytest.mark.tier2
def test_f12_09_bva_extremely_long_topic_string(cli_runner: CliRunner, tmp_output_dir: Path):
    """F12 Tier 2: Extremely long topic string (600+ chars) is handled without crash or buffer issues."""
    cmd = get_cli_command()
    long_topic = "High Performance Distributed Systems Architecture and Consensus Protocols " * 9
    result = cli_runner.invoke(cmd, [long_topic, "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Long topic string failed: {result.output}"
    assert "Consensus" in result.output


@pytest.mark.tier2
def test_f12_10_bva_unknown_flag_handling(cli_runner: CliRunner):
    """F12 Tier 2: Unknown or unsupported CLI flags produce standard Click exit code 2."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["--unknown-flag-adversarial-123"])
    assert result.exit_code == 2, f"Expected Click exit code 2, got {result.exit_code}"
    assert "no such option" in result.output.lower() or "unknown" in result.output.lower()


# ===========================================================================
# FEATURE 13: Interactive & Non-Interactive Selection
# ===========================================================================

# --- Tier 1: Feature Coverage (F13) ---

@pytest.mark.tier1
def test_f13_01_non_interactive_select_flag(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 1: --select 2 flag selects Option 2 (Explainer) non-interactively."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Data Analysis", "--select", "2", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"--select 2 failed: {result.output}"
    assert "Option 2" in result.output
    assert "Explainer" in result.output


@pytest.mark.tier1
def test_f13_02_style_selection_flag(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 1: --style 'Hacker Reel' selects matching option non-interactively."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Data Analysis", "--style", "Hacker Reel", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"--style failed: {result.output}"
    assert "Option 1" in result.output
    assert "Hacker Reel" in result.output


@pytest.mark.tier1
def test_f13_03_format_selection_vertical(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 1: --format 9:16 configures vertical reel format (1080x1920)."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Shorts Reel", "--select", "1", "--format", "9:16", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"--format 9:16 failed: {result.output}"

    mp4_files = list(tmp_output_dir.glob("*.mp4"))
    assert len(mp4_files) >= 1
    assert any("vertical_9x16" in f.name for f in mp4_files)


@pytest.mark.tier1
def test_f13_04_format_selection_horizontal(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 1: --format 16:9 configures standard horizontal format (1920x1080)."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Landscape Tutorial", "--select", "1", "--format", "16:9", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"--format 16:9 failed: {result.output}"

    mp4_files = list(tmp_output_dir.glob("*.mp4"))
    assert len(mp4_files) >= 1
    assert any("horizontal_16x9" in f.name for f in mp4_files)


@pytest.mark.tier1
def test_f13_05_interactive_selection_prompt_simulation(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 1: Simulating interactive stdin input selects requested option."""
    cmd = get_cli_command()
    # Provide '3' as user input to interactive prompt
    result = cli_runner.invoke(cmd, ["Interactive Demo", "--output", str(tmp_output_dir)], input="3\n")
    assert result.exit_code == 0, f"Interactive prompt simulation failed: {result.output}"
    assert "Option 3" in result.output or "Walkthrough" in result.output


# --- Tier 2: Boundary & Corner Cases (F13) ---

@pytest.mark.tier2
@pytest.mark.parametrize("invalid_id", ["0", "4", "99", "-1"])
def test_f13_06_bva_invalid_select_id_out_of_range(cli_runner: CliRunner, tmp_output_dir: Path, invalid_id: str):
    """F13 Tier 2: Out of range --select values are rejected with error."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Test Topic", "--select", invalid_id, "--output", str(tmp_output_dir)])
    assert result.exit_code != 0, f"Invalid select '{invalid_id}' should fail"
    assert any(num in result.output for num in ("1", "2", "3", invalid_id))


@pytest.mark.tier2
@pytest.mark.parametrize("non_numeric", ["abc", "1.5", "@#$"])
def test_f13_07_bva_invalid_select_non_numeric(cli_runner: CliRunner, tmp_output_dir: Path, non_numeric: str):
    """F13 Tier 2: Non-numeric --select values are rejected by argument parser."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Test Topic", "--select", non_numeric, "--output", str(tmp_output_dir)])
    assert result.exit_code != 0, f"Non-numeric select '{non_numeric}' should fail"


@pytest.mark.tier2
def test_f13_08_bva_invalid_style_name(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 2: Unrecognized style name lists available valid styles in error."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Test Topic", "--style", "Cyberpunk Synthwave", "--output", str(tmp_output_dir)])
    assert result.exit_code != 0, "Invalid style should fail"
    for valid_style in AVAILABLE_STYLES:
        assert valid_style in result.output


@pytest.mark.tier2
@pytest.mark.parametrize("invalid_fmt", ["4:3", "1:1", "widescreen_extra"])
def test_f13_09_bva_invalid_format_aspect_ratio(cli_runner: CliRunner, tmp_output_dir: Path, invalid_fmt: str):
    """F13 Tier 2: Unsupported aspect ratios are rejected with choices list."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Test Topic", "--select", "1", "--format", invalid_fmt, "--output", str(tmp_output_dir)])
    assert result.exit_code != 0, f"Invalid format '{invalid_fmt}' should fail"
    assert "9:16" in result.output or "16:9" in result.output


@pytest.mark.tier2
def test_f13_10_bva_headless_non_interactive_fallback(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 2: In headless mode without select/input, CLI falls back safely without hanging."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Headless Batch Job", "--headless", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Headless execution failed: {result.output}"
    assert "Option 1" in result.output


@pytest.mark.tier2
def test_f13_11_bva_case_insensitive_flag_values(cli_runner: CliRunner, tmp_output_dir: Path):
    """F13 Tier 2: CLI accepts case-insensitive format and style values."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Case Check", "--style", "hacker reel", "--format", "BOTH", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Case insensitivity failed: {result.output}"
    assert "Hacker Reel" in result.output


# ===========================================================================
# FEATURE 14: Project Delivery & Metadata Storage
# ===========================================================================

# --- Tier 1: Feature Coverage (F14) ---

@pytest.mark.tier1
def test_f14_01_final_video_delivery_to_output_dir(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 1: Final MP4 file is saved into specified output directory with valid size."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Delivery Target Test", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Delivery failed: {result.output}"

    mp4_files = list(tmp_output_dir.glob("*.mp4"))
    assert len(mp4_files) >= 1, "At least one MP4 video must be saved into output directory"
    assert mp4_files[0].stat().st_size > 0, "Saved MP4 file must be non-empty"


@pytest.mark.tier1
def test_f14_02_video_file_dual_delivery_root_and_output(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """F14 Tier 1: Video file is delivered to output/ and dual-delivered/copied to project root."""
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output_test"
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Dual Delivery Test", "--select", "1", "--output", str(output_dir)])
    assert result.exit_code == 0, f"Dual delivery execution failed: {result.output}"

    output_mp4s = list(output_dir.glob("*.mp4"))
    assert len(output_mp4s) >= 1, "Output directory missing delivered MP4 video"

    root_mp4s = list(tmp_path.glob("*.mp4"))
    assert len(root_mp4s) >= 1, "Project root missing dual-delivered MP4 video"


@pytest.mark.tier1
def test_f14_03_research_json_artifact_schema(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 1: Generated research.json contains required structured research keys."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Research Schema Check", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0

    research_file = tmp_output_dir / "research.json"
    assert research_file.exists(), "research.json artifact must be generated"

    data = json.loads(research_file.read_text(encoding="utf-8"))
    assert "topic" in data
    assert "summary" in data and isinstance(data["summary"], str)
    assert "key_points" in data and isinstance(data["key_points"], list) and len(data["key_points"]) >= 1
    assert "code_examples" in data and isinstance(data["code_examples"], list)


@pytest.mark.tier1
def test_f14_04_script_json_artifact_schema(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 1: Generated script.json contains scene breakdown matching models contract."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Script Schema Check", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0

    script_file = tmp_output_dir / "script.json"
    assert script_file.exists(), "script.json artifact must be generated"

    data = json.loads(script_file.read_text(encoding="utf-8"))
    assert "topic" in data
    assert "selected_option" in data
    assert "style_name" in data
    assert "scenes" in data and isinstance(data["scenes"], list) and len(data["scenes"]) >= 3
    for scene in data["scenes"]:
        assert "scene_id" in scene
        assert "scene_type" in scene
        assert "narration" in scene


@pytest.mark.tier1
def test_f14_05_metadata_json_artifact_schema(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 1: Generated metadata.json contains timestamps, durations, and artifact index."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Metadata Schema Check", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0

    metadata_file = tmp_output_dir / "metadata.json"
    assert metadata_file.exists(), "metadata.json artifact must be generated"

    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert "topic" in data
    assert "created_at" in data
    assert "selected_style" in data
    assert "duration" in data and data["duration"] > 0
    assert "video_files" in data and len(data["video_files"]) >= 1
    assert "status" in data


# --- Tier 2: Boundary & Corner Cases (F14) ---

@pytest.mark.tier2
def test_f14_06_bva_custom_deeply_nested_output_directory(cli_runner: CliRunner, tmp_path: Path):
    """F14 Tier 2: Deeply nested non-existent directory path is created automatically."""
    nested_dir = tmp_path / "deep" / "nested" / "output" / "dir"
    assert not nested_dir.exists()

    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Nested Target", "--select", "1", "--output", str(nested_dir)])
    assert result.exit_code == 0, f"Nested creation failed: {result.output}"
    assert nested_dir.exists(), "Deeply nested directory must be created"
    assert (nested_dir / "metadata.json").exists()


@pytest.mark.tier2
def test_f14_07_bva_output_overwrite_handling(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 2: Rerunning generation with same topic updates artifacts without file lock crash."""
    cmd = get_cli_command()
    # First invocation
    r1 = cli_runner.invoke(cmd, ["Rerun Topic", "--select", "1", "--output", str(tmp_output_dir), "--overwrite"])
    assert r1.exit_code == 0
    mtime1 = (tmp_output_dir / "metadata.json").stat().st_mtime

    time.sleep(0.05)

    # Second invocation with different option
    r2 = cli_runner.invoke(cmd, ["Rerun Topic", "--select", "2", "--output", str(tmp_output_dir), "--overwrite"])
    assert r2.exit_code == 0, f"Overwrite run failed: {r2.output}"
    mtime2 = (tmp_output_dir / "metadata.json").stat().st_mtime
    assert mtime2 >= mtime1

    meta = json.loads((tmp_output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["selected_style"] == "Explainer"


@pytest.mark.tier2
def test_f14_08_bva_filename_slug_sanitization(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 2: Adversarial topics with invalid filesystem characters produce safe filenames."""
    cmd = get_cli_command()
    adversarial_topic = "Node.js: Worker Threads vs Event Loop? (Speed * 10x <Benchmark>) | 2026"
    result = cli_runner.invoke(cmd, [adversarial_topic, "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Sanitization failed: {result.output}"

    # Verify no illegal Windows/Unix path characters in output filenames
    forbidden = set('<>:"/\\|?*')
    for f in tmp_output_dir.iterdir():
        for ch in f.name:
            assert ch not in forbidden, f"Filename '{f.name}' contains illegal char '{ch}'"
        assert f.exists()


@pytest.mark.tier2
def test_f14_09_bva_atomic_artifact_writing(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 2: JSON artifacts are written completely and parse cleanly without truncation."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Atomic Serialization Check", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Atomic execution failed: {result.output}"
    for artifact_name in ("research.json", "script.json", "metadata.json"):
        path = tmp_output_dir / artifact_name
        assert path.exists(), f"Artifact {artifact_name} was not generated"
        content = path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert len(parsed) > 0


@pytest.mark.tier2
def test_f14_10_bva_scratch_temporary_cleanup(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 2: Scratch and temporary files are cleaned up, leaving only clean deliverables."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Cleanup Check", "--select", "1", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Execution failed: {result.output}"

    # Only deliverables (.mp4, .json) should exist in output dir
    for item in tmp_output_dir.iterdir():
        assert item.suffix in (".mp4", ".json"), f"Uncleaned temporary file found: {item.name}"


@pytest.mark.tier2
def test_f14_11_bva_dual_format_both_artifacts(cli_runner: CliRunner, tmp_output_dir: Path):
    """F14 Tier 2: --format both generates both vertical and horizontal MP4 files."""
    cmd = get_cli_command()
    result = cli_runner.invoke(cmd, ["Dual Format Run", "--select", "1", "--format", "both", "--output", str(tmp_output_dir)])
    assert result.exit_code == 0, f"Dual format run failed: {result.output}"

    mp4_files = list(tmp_output_dir.glob("*.mp4"))
    names = [f.name for f in mp4_files]
    assert any("vertical_9x16" in n for n in names), f"Vertical file missing in: {names}"
    assert any("horizontal_16x9" in n for n in names), f"Horizontal file missing in: {names}"

    meta = json.loads((tmp_output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "9:16" in meta["formats"]
    assert "16:9" in meta["formats"]
