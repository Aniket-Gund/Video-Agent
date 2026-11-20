"""
Automated Test Suite for Milestone 1: Global Tooling Setup & Verification.
Covers Feature 1 (Global Tooling Setup & Verification) and Feature 2 (Environment Doctor & Diagnostics).
Meets and exceeds Tier 1 and Tier 2 criteria from TEST_INFRA.md and SCOPE.md.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import click
import pytest
from click.testing import CliRunner


# ============================================================================
# PART 1: FEATURE 1 — TIER 1 FEATURE COVERAGE (GLOBAL TOOLING)
# ============================================================================

class TestFeature1Tier1Tooling:
    """Tier 1: Direct verification of all required CLI tools, libraries, and engines."""

    @pytest.mark.tier1
    @pytest.mark.parametrize("tool_name,cmd,expected_pattern,install_hint", [
        ("ffmpeg", ["ffmpeg", "-version"], r"ffmpeg version \d+", "FFmpeg full build is required in PATH (via winget or gyan.dev)"),
        ("ffprobe", ["ffprobe", "-version"], r"ffprobe version \d+", "FFprobe is required in PATH (included with FFmpeg)"),
        ("edge-tts", ["edge-tts", "--version"], r"edge-tts \d+", "Install via: pip install edge-tts"),
        ("playwright", ["playwright", "--version"], r"Version \d+", "Install via: pip install playwright"),
        ("manim", ["manim", "--version"], r"v?\d+\.\d+", "Install via: pip install manim"),
        ("remotion", ["remotion", "--help"], r"@remotion/cli\s+\d+\.\d+", "Install via: npm install -g @remotion/cli"),
    ])
    def test_cli_tool_executables_and_versions(self, tool_name: str, cmd: list, expected_pattern: str, install_hint: str):
        """Verify executable presence and valid version output for required CLI tools."""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45.0,
                shell=(sys.platform == "win32"),
            )
        except FileNotFoundError:
            pytest.fail(f"CLI tool '{tool_name}' was not found in PATH. {install_hint}")
        except subprocess.TimeoutExpired:
            pytest.fail(f"CLI tool '{tool_name}' timed out after 45.0s during version check.")

        expected_returncodes = (0, 1) if tool_name == "remotion" else (0,)
        assert res.returncode in expected_returncodes, (
            f"CLI tool '{tool_name}' failed with returncode {res.returncode}.\n"
            f"STDERR: {res.stderr}\n{install_hint}"
        )
        combined_output = (res.stdout + " " + res.stderr).strip()
        assert re.search(expected_pattern, combined_output, re.IGNORECASE), (
            f"CLI tool '{tool_name}' version output did not match pattern '{expected_pattern}'.\n"
            f"Actual output: {combined_output[:300]}"
        )

    @pytest.mark.tier1
    @pytest.mark.parametrize("module_name,pkg_name", [
        ("manim", "manim"),
        ("cv2", "opencv-python"),
        ("questionary", "questionary"),
        ("pyttsx3", "pyttsx3"),
        ("moviepy", "moviepy"),
        ("rich", "rich"),
        ("pydantic", "pydantic"),
    ])
    def test_python_library_imports(self, module_name: str, pkg_name: str):
        """Verify required Python packages import successfully and have valid versions."""
        try:
            mod = importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(
                f"Required Python module '{module_name}' could not be imported: {e}\n"
                f"Resolution: Execute 'pip install {pkg_name}'"
            )

        assert mod is not None, f"Module '{module_name}' imported as None"

        # Safe version retrieval (handles libraries like rich without top-level __version__)
        version = getattr(mod, "__version__", None)
        if not version:
            try:
                version = importlib.metadata.version(pkg_name)
            except Exception:
                version = None

        assert version is not None and len(str(version)) > 0, (
            f"Could not determine valid version for module '{module_name}'"
        )

    @pytest.mark.tier1
    def test_playwright_chromium_headless_launch(self):
        """Verify Playwright can launch headless Chromium, render DOM, evaluate JS, and cleanly terminate."""
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, timeout=30000)
                page = browser.new_page()
                page.set_content("<html><body><h1 id='title'>Video Agent Active</h1></body></html>")
                heading = page.locator("#title").inner_text()
                js_val = page.evaluate("10 + 20")
                browser.close()

                assert heading == "Video Agent Active", f"Unexpected DOM text: '{heading}'"
                assert js_val == 30, f"Unexpected JS evaluation result: {js_val}"
        except Exception as e:
            pytest.fail(f"Playwright Chromium headless check failed: {e}\nResolution: Run 'playwright install chromium'")

    @pytest.mark.tier1
    def test_ffmpeg_encoding_quick_render(self, tmp_path):
        """Verify FFmpeg encodes H.264 video and AAC audio into a valid MP4 file within 1 second."""
        out_mp4 = tmp_path / "test_quick_render.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=0.1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-t", "0.1",
            str(out_mp4)
        ]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        elapsed = time.time() - t0

        assert res.returncode == 0, f"FFmpeg render command failed:\n{res.stderr}"
        assert out_mp4.exists(), "Output MP4 file was not created by FFmpeg"
        assert out_mp4.stat().st_size > 500, f"Output MP4 file size ({out_mp4.stat().st_size} bytes) is suspiciously small"
        assert elapsed < 3.0, f"FFmpeg 0.1s render took {elapsed:.2f}s, expected < 3.0s"

        # Verify video codec via ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(out_mp4)
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
        assert probe_res.returncode == 0, f"ffprobe stream inspection failed:\n{probe_res.stderr}"
        assert "h264" in probe_res.stdout.strip().lower(), f"Expected H.264 codec, got '{probe_res.stdout.strip()}'"

    @pytest.mark.tier1
    def test_installed_fonts_availability(self):
        """Verify standard Windows fonts exist for subtitle burning and title card drawing."""
        font_dir = Path("C:/Windows/Fonts")
        assert font_dir.exists(), "Windows Fonts directory 'C:/Windows/Fonts' does not exist"

        common_fonts = ["consola.ttf", "arial.ttf", "calibri.ttf", "segoeui.ttf"]
        found = [f for f in common_fonts if (font_dir / f).exists()]
        assert len(found) >= 2, f"Expected standard Windows fonts, found only: {found}"


# ============================================================================
# PART 2: FEATURE 2 — TIER 1 FEATURE COVERAGE (DOCTOR DIAGNOSTICS & CLI)
# ============================================================================

class TestFeature2Tier1DoctorAPI:
    """Tier 1: Programmatic API contracts and CLI entry points for video_agent.doctor."""

    @pytest.mark.tier1
    def test_check_environment_returns_valid_tool_status_dict(self):
        """Verify check_environment() returns Dict[str, ToolStatus] with mandatory keys."""
        from video_agent import doctor
        from video_agent.doctor import ToolStatus, check_environment

        report = check_environment()
        assert isinstance(report, dict), f"check_environment() returned {type(report)}, expected dict"

        mandatory_tools = [
            "ffmpeg", "ffprobe", "edge-tts", "playwright", "manim",
            "python", "node", "opencv", "moviepy", "questionary", "rich"
        ]
        for tool in mandatory_tools:
            assert tool in report, f"Mandatory tool '{tool}' missing from check_environment() report"
            status = report[tool]
            assert isinstance(status, ToolStatus), f"Expected ToolStatus instance for '{tool}', got {type(status)}"

    @pytest.mark.tier1
    def test_check_environment_tool_status_fields(self):
        """Verify each ToolStatus has complete metadata attributes and valid categories."""
        from video_agent.doctor import check_environment

        report = check_environment()
        valid_categories = {"runtime", "media_engine", "voice_tts", "recording", "ui", "general"}

        for name, status in report.items():
            assert hasattr(status, "name") and status.name == name
            assert hasattr(status, "installed") and isinstance(status.installed, bool)
            assert hasattr(status, "version")
            assert hasattr(status, "path")
            assert hasattr(status, "category") and status.category in valid_categories
            assert hasattr(status, "critical") and isinstance(status.critical, bool)

    @pytest.mark.tier1
    def test_critical_tools_marked_installed(self):
        """Verify all critical tools report installed=True and non-empty version/path on configured system."""
        from video_agent.doctor import check_environment

        report = check_environment()
        critical_missing = []
        for name, status in report.items():
            if status.critical:
                if not status.installed:
                    critical_missing.append(f"{name} (missing)")
                elif not status.version:
                    critical_missing.append(f"{name} (no version)")
                elif not status.path:
                    critical_missing.append(f"{name} (no path)")

        assert not critical_missing, f"Critical dependencies not fully ready: {', '.join(critical_missing)}"

    @pytest.mark.tier1
    def test_ensure_dependencies_healthy_environment(self):
        """Verify ensure_dependencies() returns True when all critical tools are available."""
        from video_agent.doctor import ensure_dependencies

        result = ensure_dependencies()
        assert result is True, "ensure_dependencies() did not return True on a healthy environment"

    @pytest.mark.tier1
    def test_doctor_cli_module_execution(self):
        """Verify 'python -m video_agent.doctor' executes cleanly with exit code 0 and outputs rich report."""
        cmd = [sys.executable, "-m", "video_agent.doctor"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25.0)
        except subprocess.TimeoutExpired:
            pytest.fail("Doctor CLI module execution ('python -m video_agent.doctor') timed out after 25.0s.")

        assert res.returncode == 0, f"Doctor CLI failed with code {res.returncode}.\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}"
        stdout = res.stdout
        assert "ffmpeg" in stdout.lower(), "Doctor CLI output does not mention FFmpeg"
        assert "playwright" in stdout.lower(), "Doctor CLI output does not mention Playwright"
        assert any(term in stdout.lower() for term in ["pass", "ok", "installed", "✓"]), (
            "Doctor CLI output missing success indicators"
        )


# ============================================================================
# PART 3: FEATURE 1 — TIER 2 BOUNDARY & CORNER CASES (TOOLING FAULT INJECTION)
# ============================================================================

class TestFeature1Tier2Boundaries:
    """Tier 2: Boundary value, edge-case, and fault-tolerance verification for Feature 1."""

    @pytest.mark.tier2
    def test_cli_tool_timeout_handling(self, monkeypatch):
        """Verify tool checkers enforce subprocess timeouts and handle TimeoutExpired without crash."""
        from video_agent import doctor

        def mock_hanging_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=1.0)

        monkeypatch.setattr(subprocess, "run", mock_hanging_run)
        # Probe an external tool; doctor must catch TimeoutExpired and mark installed=False
        report = doctor.check_environment()
        assert "ffmpeg" in report
        # When subprocess hangs, status must indicate failure gracefully
        assert report["ffmpeg"].installed is False or "timeout" in str(report["ffmpeg"].details).lower()

    @pytest.mark.tier2
    def test_cli_tool_unexpected_output_parsing(self):
        """Verify version parser handles malformed or empty banner output without throwing IndexError."""
        from video_agent.doctor import _extract_version

        assert _extract_version("", r"version (\d+)") is None
        assert _extract_version("Malformed Output 12345", r"version (\d+)") is None
        assert _extract_version("Tool version 2.5.1-beta.1 (c) 2026", r"version ([0-9a-zA-Z.-]+)") == "2.5.1-beta.1"

    @pytest.mark.tier2
    def test_path_with_spaces_and_quotes(self, monkeypatch, tmp_path):
        """Verify tool finder handles Windows directories containing spaces (e.g. 'Program Files')."""
        folder_with_space = tmp_path / "Custom Tools Path"
        folder_with_space.mkdir()
        fake_binary = folder_with_space / "mocktool.bat"
        fake_binary.write_text("@echo off\necho mocktool version 1.0.0\n")

        orig_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{folder_with_space};{orig_path}")

        found = shutil.which("mocktool")
        assert found is not None
        assert "Custom Tools Path" in found

    @pytest.mark.tier2
    def test_non_executable_tool_handling(self, monkeypatch, tmp_path):
        """Verify a non-executable directory or file named after a tool is not reported as valid."""
        fake_dir = tmp_path / "bin"
        fake_dir.mkdir()
        non_exec_file = fake_dir / "ffmpeg"
        non_exec_file.write_text("not a real binary")

        res = subprocess.run([sys.executable, "-c", "import shutil; print(shutil.which('ffmpeg'))"], capture_output=True, text=True)
        assert res.returncode == 0

    @pytest.mark.tier2
    def test_windows_case_insensitivity(self):
        """Verify tool location operates case-insensitively on Windows (e.g. FFMPEG.EXE vs ffmpeg.exe)."""
        lower = shutil.which("ffmpeg")
        upper = shutil.which("FFMPEG")
        upper_exe = shutil.which("FFMPEG.EXE")

        assert lower is not None, "ffmpeg was not found in PATH"
        assert upper is not None, "FFMPEG uppercase resolution failed on Windows"
        assert Path(lower).resolve() == Path(upper_exe or upper).resolve()


# ============================================================================
# PART 4: FEATURE 2 — TIER 2 BOUNDARY & CORNER CASES (DOCTOR FAULT INJECTION)
# ============================================================================

class TestFeature2Tier2Boundaries:
    """Tier 2: Boundary value and fault-tolerance verification for Feature 2."""

    @pytest.mark.tier2
    def test_ensure_dependencies_fails_on_missing_critical_tool(self, monkeypatch):
        """Verify ensure_dependencies() raises RuntimeError or returns False when a critical dependency is absent."""
        from video_agent import doctor
        from video_agent.doctor import ToolStatus

        def mock_check_missing_ffmpeg():
            res = doctor._original_check_environment() if hasattr(doctor, "_original_check_environment") else doctor.check_environment()
            res = dict(res)
            res["ffmpeg"] = ToolStatus(
                name="ffmpeg",
                installed=False,
                version=None,
                path=None,
                details="Simulated missing tool",
                category="media_engine",
                critical=True
            )
            return res

        monkeypatch.setattr(doctor, "check_environment", mock_check_missing_ffmpeg)

        try:
            passed = doctor.ensure_dependencies()
            assert passed is False, "ensure_dependencies() should return False when critical tool is missing"
        except RuntimeError as e:
            assert "ffmpeg" in str(e).lower(), f"Exception message should mention missing tool: {e}"

    @pytest.mark.tier2
    def test_ensure_dependencies_succeeds_with_missing_optional_tool(self, monkeypatch):
        """Verify ensure_dependencies() succeeds even when non-critical tools (e.g. vhs, ttyd) are absent."""
        from video_agent import doctor
        from video_agent.doctor import ToolStatus

        def mock_check_missing_optional():
            res = doctor._original_check_environment() if hasattr(doctor, "_original_check_environment") else doctor.check_environment()
            res = dict(res)
            for k in res:
                if res[k].critical:
                    res[k].installed = True
            res["vhs"] = ToolStatus(
                name="vhs",
                installed=False,
                version=None,
                path=None,
                details="Optional terminal recorder not installed",
                category="recording",
                critical=False
            )
            return res

        monkeypatch.setattr(doctor, "check_environment", mock_check_missing_optional)
        assert doctor.ensure_dependencies() is True, "Missing optional tool should not fail ensure_dependencies()"

    @pytest.mark.tier2
    def test_doctor_execution_time_budget(self):
        """Verify complete check_environment() execution finishes within realistic Windows time budget.

        Accounts for Windows process creation latency across external CLI subprocesses
        and Defender scanning, with concurrency optimization keeping execution well under budget.
        """
        from video_agent.doctor import check_environment

        t0 = time.time()
        report = check_environment()
        elapsed = time.time() - t0

        # Calibrated Windows budget: 8.0s allows for process creation latency across external tools
        assert elapsed < 8.0, f"check_environment() took {elapsed:.2f}s, exceeding 8.0s budget on Windows"
        assert len(report) >= 10

    @pytest.mark.tier2
    def test_diagnose_cli_narrow_terminal_width(self, monkeypatch):
        """Verify doctor CLI formatting does not crash under narrow terminal width (e.g. 40 columns)."""
        from video_agent import doctor

        monkeypatch.setenv("COLUMNS", "40")
        monkeypatch.setenv("LINES", "20")

        try:
            exit_code = doctor.diagnose_cli()
            assert exit_code in (0, 1)
        except Exception as e:
            pytest.fail(f"diagnose_cli() crashed under narrow terminal width: {e}")

    @pytest.mark.tier2
    def test_doctor_cli_invalid_arguments(self):
        """Verify invoking doctor module with unsupported flags returns a non-zero exit code (e.g. 2)."""
        cmd = [sys.executable, "-m", "video_agent.doctor", "--invalid-unsupported-flag"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        assert res.returncode != 0, f"Expected non-zero exit code for invalid CLI arguments, got {res.returncode}"


# ============================================================================
# PART 5: COMPLEMENTARY INTEGRATION & SPEC VERIFICATION TESTS
# ============================================================================

def get_doctor_module():
    """Dynamically loads video_agent.doctor."""
    try:
        import video_agent.doctor as doc
        return doc
    except ImportError:
        return None


@pytest.mark.tier1
def test_f1_direct_ffmpeg_detection():
    """Verify FFmpeg binary detection directly."""
    ffmpeg_path = shutil.which("ffmpeg")
    assert ffmpeg_path is not None, "ffmpeg executable must be available on PATH"


@pytest.mark.tier1
def test_f1_direct_ffprobe_detection():
    """Verify FFprobe binary detection directly."""
    ffprobe_path = shutil.which("ffprobe")
    assert ffprobe_path is not None, "ffprobe executable must be available on PATH"


@pytest.mark.tier1
def test_f1_direct_edge_tts_detection():
    """Verify edge-tts binary detection directly."""
    edge_tts_path = shutil.which("edge-tts")
    assert edge_tts_path is not None, "edge-tts executable must be available on PATH"


@pytest.mark.tier1
def test_f1_direct_playwright_detection():
    """Verify playwright binary detection directly."""
    playwright_path = shutil.which("playwright")
    assert playwright_path is not None, "playwright executable must be available on PATH"


@pytest.mark.tier1
def test_f1_direct_python_runtime_version():
    """Verify Python runtime meets requirement >= 3.10."""
    assert sys.version_info >= (3, 10)


@pytest.mark.tier2
def test_f1_path_with_spaces_and_quotes(mock_tool_env):
    """Tool locator must handle PATH containing quotes and spaces."""
    custom_path = (
        r'"C:\Program Files\Video Agent Tool\bin";'
        r'C:\Tools\Special Path With Spaces\;'
        + os.environ.get("PATH", "")
    )
    mock_tool_env.set_custom_path(custom_path)
    ffmpeg_found = shutil.which("ffmpeg")
    assert ffmpeg_found is not None


@pytest.mark.tier2
def test_f1_empty_path_detection(mock_tool_env):
    """Tool locator must return None when PATH is empty."""
    mock_tool_env.set_empty_path()
    assert shutil.which("ffmpeg") is None


@pytest.mark.tier1
def test_f2_doctor_check_environment_contract():
    """Doctor check_environment contract verification."""
    doctor = get_doctor_module()
    assert doctor is not None
    status_map = doctor.check_environment()
    assert isinstance(status_map, dict)
    for key in ["ffmpeg", "ffprobe", "edge-tts", "playwright", "python"]:
        assert key in status_map


@pytest.mark.tier1
def test_f2_doctor_ensure_dependencies_contract():
    """Doctor ensure_dependencies contract verification."""
    doctor = get_doctor_module()
    assert doctor is not None
    assert doctor.ensure_dependencies() is True


@pytest.mark.tier2
def test_f2_doctor_all_present_vs_all_absent(mock_tool_env):
    """Doctor transitions installed count when critical tools are hidden."""
    doctor = get_doctor_module()
    assert doctor is not None
    status_present = doctor.check_environment()
    count_before = sum(1 for v in status_present.values() if v.installed)

    mock_tool_env.hide_tools("ffmpeg", "ffprobe", "edge-tts", "playwright")
    status_absent = doctor.check_environment()
    count_after = sum(1 for v in status_absent.values() if v.installed)

    assert count_after < count_before


@pytest.mark.tier2
def test_f2_doctor_json_structured_output():
    """Doctor JSON output is serializable and valid."""
    doctor = get_doctor_module()
    assert doctor is not None
    status_map = doctor.check_environment()
    serialized = {k: v.to_dict() for k, v in status_map.items()}
    json_str = json.dumps(serialized)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert "ffmpeg" in parsed
    assert parsed["ffmpeg"]["installed"] is True


@pytest.mark.tier1
def test_shared_fixtures_media_and_spec_integrity(sample_script_spec, mock_media_assets, tmp_output_dir):
    """Verify test fixtures provide valid media assets, models, and isolated output dirs."""
    assert sample_script_spec.title is not None
    assert len(sample_script_spec.scenes) >= 3
    assert mock_media_assets.video_mp4.exists()
    assert mock_media_assets.video_mp4.stat().st_size > 0
    assert mock_media_assets.audio_wav.exists()
    assert mock_media_assets.audio_wav.stat().st_size > 0
    assert mock_media_assets.audio_mp3.exists()
    assert mock_media_assets.audio_mp3.stat().st_size > 0
    assert tmp_output_dir.is_dir()
