"""Shared pytest fixtures for Video Agent test suites.

Provides isolated test environments, CLI test runner, mock media assets,
sample pipeline data models matching PROJECT.md interface contracts,
and environment doctor test helpers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct pytest invocation
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import shutil
import subprocess
from enum import Enum
from typing import Any, Dict, List, Optional

import pytest
from click.testing import CliRunner
from pydantic import BaseModel, Field


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers to prevent PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage tests")
    config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Cases")
    config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Combination tests")
    config.addinivalue_line("markers", "tier4: Tier 4 Realistic Scenario tests")
    config.addinivalue_line("markers", "e2e: End-to-end integration tests")

# ---------------------------------------------------------------------------
# Interface Contract Models (PROJECT.md § Interface Contracts)
# ---------------------------------------------------------------------------
try:
    from video_agent.models import SceneSpec, SceneType, VideoOptionSpec
except ImportError:
    class SceneType(str, Enum):
        INTRO = "intro"
        CONCEPT = "concept"
        CODE_EXECUTION = "code_execution"
        OUTRO = "outro"

    class SceneSpec(BaseModel):
        scene_id: str
        scene_type: SceneType
        narration: str
        visual_prompt: str
        code_snippet: Optional[str] = None
        command: Optional[str] = None
        audio_file: Optional[Path] = None
        audio_duration: float = 0.0
        subtitles_srt: Optional[Path] = None
        visual_clip: Optional[Path] = None

    class VideoOptionSpec(BaseModel):
        option_id: int
        style_name: str
        title: str
        tagline: str
        voice_name: str
        scenes: List[SceneSpec]
        estimated_duration: float
        visual_theme: Dict[str, Any]


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing a Click CliRunner instance for testing CLI commands."""
    return CliRunner()


@pytest.fixture(autouse=True)
def clean_workspace_root_after_test():
    """Autouse fixture ensuring no .mp4 files leaked into the workspace root during any test."""
    yield
    for mp4_file in _PROJECT_ROOT.glob("*.mp4"):
        try:
            mp4_file.unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary directory for test media outputs."""
    out_dir = tmp_path / "video_agent_test_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


@pytest.fixture
def sample_script_spec() -> VideoOptionSpec:
    """Fixture returning a valid VideoOptionSpec object matching PROJECT.md interface contracts."""
    scenes = [
        SceneSpec(
            scene_id="scene_001_intro",
            scene_type=SceneType.INTRO,
            narration="Welcome to extreme performance computing in Python.",
            visual_prompt="Glowing neon terminal with animated glitch title card",
            audio_duration=3.5,
        ),
        SceneSpec(
            scene_id="scene_002_concept",
            scene_type=SceneType.CONCEPT,
            narration="Vectorization shifts loop processing from slow bytecode to SIMD registers.",
            visual_prompt="Diagram displaying CPU vector registers processing matrix rows in parallel",
            audio_duration=4.2,
        ),
        SceneSpec(
            scene_id="scene_003_demo",
            scene_type=SceneType.CODE_EXECUTION,
            narration="Here we run NumPy vector operations achieving a 50x speed boost.",
            visual_prompt="Terminal playback of benchmark script executing in real time",
            code_snippet=(
                "import numpy as np\n"
                "x = np.random.randn(1000000)\n"
                "y = np.sum(x ** 2)\n"
                "print(f'Computed sum of squares: {y:.2f}')"
            ),
            command="python benchmark.py",
            audio_duration=5.0,
        ),
        SceneSpec(
            scene_id="scene_004_outro",
            scene_type=SceneType.OUTRO,
            narration="Follow for daily high-performance software engineering patterns.",
            visual_prompt="Modern end screen with glowing social call-to-actions",
            audio_duration=2.8,
        ),
    ]

    return VideoOptionSpec(
        option_id=1,
        style_name="Hacker Reel",
        title="100x Faster Python with NumPy Vectorization",
        tagline="Unlock extreme speed in 60 seconds",
        voice_name="en-US-ChristopherNeural",
        scenes=scenes,
        estimated_duration=15.5,
        visual_theme={
            "primary_color": "#00FF66",
            "background_color": "#0A0A0A",
            "font_family": "Consolas",
            "accent_color": "#00E5FF",
            "aspect_ratio": "9:16",
        },
    )


class MediaAssetBundle:
    """Helper class exposing media files via attributes and dictionary lookup."""
    def __init__(self, video_mp4: Path, audio_wav: Path, audio_mp3: Path):
        self.video_mp4 = video_mp4
        self.audio_wav = audio_wav
        self.audio_mp3 = audio_mp3

    def __getitem__(self, key: str) -> Path:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"MediaAssetBundle has no asset '{key}'")


@pytest.fixture
def mock_media_assets(tmp_path: Path) -> MediaAssetBundle:
    """Fixture generating a valid tiny test MP4 video and test WAV/MP3 audio."""
    assets_dir = tmp_path / "mock_media"
    assets_dir.mkdir(parents=True, exist_ok=True)

    video_path = assets_dir / "tiny_test_video.mp4"
    audio_wav = assets_dir / "tiny_test_audio.wav"
    audio_mp3 = assets_dir / "tiny_test_audio.mp3"

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        # Generate tiny 1-second 160x120 test MP4 video
        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15.0,
            check=False,
        )

        # Generate tiny 1-second 440Hz sine wave WAV audio
        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "pcm_s16le",
                str(audio_wav),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15.0,
            check=False,
        )

        # Generate tiny 1-second 440Hz sine wave MP3 audio
        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "libmp3lame",
                str(audio_mp3),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15.0,
            check=False,
        )

    # Standalone synthetic fallback if ffmpeg was not reachable or failed
    if not video_path.exists() or video_path.stat().st_size == 0:
        video_path.write_bytes(
            b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free"
            b"\x00\x00\x00\x10mdat12345678\x00\x00\x00\x10moov12345678"
        )
    if not audio_wav.exists() or audio_wav.stat().st_size == 0:
        # Minimal valid 44-byte WAV header (PCM 44.1kHz 16-bit mono)
        header = (
            b"RIFF\x28\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x04\x00\x00\x00\x00\x00\x00\x00"
        )
        audio_wav.write_bytes(header)
    if not audio_mp3.exists() or audio_mp3.stat().st_size == 0:
        # Minimal valid MP3 sync frame
        audio_mp3.write_bytes(b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00")

    return MediaAssetBundle(video_path, audio_wav, audio_mp3)


class ToolEnvController:
    """Helper controller to manipulate tool detection and PATH for doctor testing."""
    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.monkeypatch = monkeypatch
        self._orig_which = shutil.which
        self._orig_subprocess_run = subprocess.run

    def hide_tools(self, *tool_names: str) -> None:
        """Hides specified tools from shutil.which (case- and extension-insensitive)."""
        hidden = {name.lower().removesuffix(".exe").removesuffix(".cmd") for name in tool_names}

        def mocked_which(cmd: str, *args, **kwargs):
            base = Path(cmd).stem.lower()
            if cmd in hidden or base in hidden or cmd.lower() in hidden:
                return None
            return self._orig_which(cmd, *args, **kwargs)

        self.monkeypatch.setattr(shutil, "which", mocked_which)

    def hide_binary(self, binary_name: str) -> None:
        """Hides single binary from shutil.which (alias for hide_tools)."""
        self.hide_tools(binary_name)

    def set_empty_path(self) -> None:
        """Sets PATH to empty string."""
        self.monkeypatch.setenv("PATH", "")

    def set_custom_path(self, path_str: str) -> None:
        """Sets custom PATH string."""
        self.monkeypatch.setenv("PATH", path_str)

    def mock_tool_output(self, tool_name: str, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        """Intercepts subprocess.run for a tool to return custom output, handling text/binary modes cleanly."""
        orig_run = self._orig_subprocess_run

        def custom_run(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if tool_name.lower() in cmd_str.lower():
                is_text = kwargs.get("text") or kwargs.get("universal_newlines")
                out = stdout if is_text or isinstance(stdout, str) else stdout.encode("utf-8")
                err = stderr if is_text or isinstance(stderr, str) else stderr.encode("utf-8")
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=returncode,
                    stdout=out,
                    stderr=err,
                )
            return orig_run(cmd, *args, **kwargs)

        self.monkeypatch.setattr(subprocess, "run", custom_run)

    def mock_tool_timeout(self, tool_name: str, timeout_seconds: float = 2.0) -> None:
        """Intercepts subprocess.run for a tool to simulate a timeout."""
        orig_run = self._orig_subprocess_run

        def custom_run(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if tool_name.lower() in cmd_str.lower():
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_seconds)
            return orig_run(cmd, *args, **kwargs)

        self.monkeypatch.setattr(subprocess, "run", custom_run)


@pytest.fixture
def mock_tool_env(monkeypatch: pytest.MonkeyPatch) -> ToolEnvController:
    """Fixture to simulate missing, corrupted, or custom tool environments for doctor diagnostics."""
    return ToolEnvController(monkeypatch)
