"""
video_agent.visual.recorder - Headless code execution and terminal recording engine.

Simulates terminal recording of executing code snippets with syntax highlighting
and window chrome rendered to MP4 video files via FFmpeg.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from video_agent.models import SceneSpec

logger = logging.getLogger(__name__)


def _get_mono_font(size: int) -> ImageFont.ImageFont:
    """Load monospaced TrueType font."""
    font_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
    for font_file in ["consola.ttf", "cour.ttf", "segoeui.ttf"]:
        p = font_dir / font_file
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """Parse hex color string to RGB."""
    if not hex_color or not isinstance(hex_color, str):
        return default
    c = hex_color.strip().lstrip("#")
    if len(c) == 6:
        try:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        except ValueError:
            pass
    return default


def render_code_execution_scene(
    scene: Any,
    duration: float,
    width: int,
    height: int,
    theme: Dict[str, Any],
    output_path: Path,
) -> Path:
    """Record a code execution / terminal demo scene to an MP4 video file.

    Parameters
    ----------
    scene : SceneSpec
        The scene specification containing code_snippet, command, etc.
    duration : float
        Target duration in seconds for the output clip.
    width : int
        Output video width in pixels.
    height : int
        Output video height in pixels.
    theme : dict
        Visual theme configuration.
    output_path : Path
        Destination path for the rendered MP4 file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fps = 30
    duration = max(0.5, float(duration))

    scale = min(width / 1920, height / 1080)
    font_size = max(14, int(26 * scale))
    header_font_size = max(12, int(20 * scale))

    code_font = _get_mono_font(font_size)
    header_font = _get_mono_font(header_font_size)

    # Colors
    bg_color = _hex_to_rgb(theme.get("background_color", "#0A0A0A"), (10, 10, 10))
    terminal_bg = (18, 22, 28)
    primary_color = _hex_to_rgb(theme.get("primary_color", "#00FF66"), (0, 255, 102))
    accent_color = _hex_to_rgb(theme.get("accent_color", "#00E5FF"), (0, 229, 255))
    text_color = (220, 225, 230)
    comment_color = (120, 130, 140)

    code_snippet = getattr(scene, "code_snippet", "") or ""
    command = getattr(scene, "command", "") or "python demo.py"

    lines: List[str] = [f"$ {command}"]
    if code_snippet:
        lines.extend(code_snippet.splitlines())
    else:
        lines.extend([
            "import time",
            "print('Starting execution pipeline...')",
            "time.sleep(0.5)",
            "print('Optimization complete: 100% verified')",
        ])

    frame = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(frame)

    margin_x = int(width * 0.08)
    margin_y = int(height * 0.12)
    box_w = width - 2 * margin_x
    box_h = height - 2 * margin_y

    header_h = max(24, int(42 * scale))
    dot_radius = max(4, int(7 * scale))

    # Terminal Window Outer
    draw.rectangle(
        [(margin_x, margin_y), (margin_x + box_w, margin_y + box_h)],
        fill=terminal_bg,
        outline=accent_color,
        width=max(1, int(2 * scale)),
    )

    # Window Title Bar
    draw.rectangle(
        [(margin_x, margin_y), (margin_x + box_w, margin_y + header_h)],
        fill=(28, 34, 42),
    )

    # Window Buttons
    dot_y = margin_y + header_h // 2
    dot_x1 = margin_x + int(24 * scale)
    draw.ellipse([(dot_x1 - dot_radius, dot_y - dot_radius), (dot_x1 + dot_radius, dot_y + dot_radius)], fill=(255, 95, 87))
    dot_x2 = dot_x1 + int(20 * scale)
    draw.ellipse([(dot_x2 - dot_radius, dot_y - dot_radius), (dot_x2 + dot_radius, dot_y + dot_radius)], fill=(254, 188, 46))
    dot_x3 = dot_x2 + int(20 * scale)
    draw.ellipse([(dot_x3 - dot_radius, dot_y - dot_radius), (dot_x3 + dot_radius, dot_y + dot_radius)], fill=(39, 201, 63))

    title_text = f"terminal -- {command}"
    draw.text((margin_x + box_w // 2, dot_y), title_text, font=header_font, fill=(160, 170, 180), anchor="mm")

    # Render Code Lines
    cur_y = margin_y + header_h + int(16 * scale)
    line_h = int(font_size * 1.45)

    for l_idx, line in enumerate(lines):
        if cur_y + line_h > margin_y + box_h - int(10 * scale):
            break
        text_x = margin_x + int(20 * scale)
        fill_col = primary_color if l_idx == 0 else (comment_color if line.strip().startswith("#") else text_color)
        draw.text((text_x, cur_y), line, font=code_font, fill=fill_col)
        cur_y += line_h

    # Add cursor on prompt line or last line
    draw.text((margin_x + int(20 * scale), cur_y), "█", font=code_font, fill=accent_color)

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise FileNotFoundError("ffmpeg not found on PATH.")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_png = tmp_file.name

    try:
        frame.save(tmp_png, format="PNG")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-loop", "1",
            "-framerate", str(fps),
            "-t", f"{duration:.3f}",
            "-i", tmp_png,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg code recording failed (exit {res.returncode})")
    finally:
        try:
            os.unlink(tmp_png)
        except OSError:
            pass

    return output_path
