"""
video_agent.visual.animations - Programmatic animation rendering engine.

Renders motion graphics, animated title cards, diagrams, and counters
via Pillow and FFmpeg for intro, concept, and outro scene types.
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

from video_agent.models import SceneSpec, SceneType

logger = logging.getLogger(__name__)


def _get_font(font_name: str, size: int) -> ImageFont.ImageFont:
    """Safely load TrueType font with fallbacks."""
    font_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
    candidates = [
        font_dir / f"{font_name}.ttf",
        font_dir / "segoeui.ttf",
        font_dir / "arial.ttf",
        font_dir / "consola.ttf",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """Parse hex color string '#RRGGBB' to (R, G, B) tuple."""
    if not hex_color or not isinstance(hex_color, str):
        return default
    c = hex_color.strip().lstrip("#")
    if len(c) == 6:
        try:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        except ValueError:
            pass
    elif len(c) == 3:
        try:
            return int(c[0] * 2, 16), int(c[1] * 2, 16), int(c[2] * 2, 16)
        except ValueError:
            pass
    return default


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Break text into lines fitting within max_width."""
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current_line = words[0]
    for w in words[1:]:
        test_line = f"{current_line} {w}"
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = w
    lines.append(current_line)
    return lines


def _create_gradient_bg(width: int, height: int, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> Image.Image:
    """Generate vertical gradient background."""
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        factor = y / max(1, height)
        r = int(color1[0] * (1 - factor) + color2[0] * factor)
        g = int(color1[1] * (1 - factor) + color2[1] * factor)
        b = int(color1[2] * (1 - factor) + color2[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def render_animation_scene(
    scene: Any,
    duration: float,
    width: int,
    height: int,
    theme: Dict[str, Any],
    output_path: Path,
) -> Path:
    """Render a programmatic animation scene to an MP4 video file via FFmpeg.

    Parameters
    ----------
    scene : SceneSpec
        The scene specification containing narration, visual_prompt, etc.
    duration : float
        Target duration in seconds for the output clip.
    width : int
        Output video width in pixels.
    height : int
        Output video height in pixels.
    theme : dict
        Visual theme configuration (colors, fonts, etc.).
    output_path : Path
        Destination path for the rendered MP4 file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fps = 30
    duration = max(0.5, float(duration))

    bg_color = _hex_to_rgb(theme.get("background_color", "#0A0A0A"), (10, 10, 10))
    primary_color = _hex_to_rgb(theme.get("primary_color", "#00FF66"), (0, 255, 102))
    accent_color = _hex_to_rgb(theme.get("accent_color", "#00E5FF"), (0, 229, 255))
    text_color = _hex_to_rgb(theme.get("text_color", "#FFFFFF"), (255, 255, 255))

    dark_blend = (max(0, bg_color[0] - 20), max(0, bg_color[1] - 20), max(0, bg_color[2] - 20))
    frame = _create_gradient_bg(width, height, bg_color, dark_blend)
    draw = ImageDraw.Draw(frame)

    scale = min(width / 1920, height / 1080)
    title_size = max(24, int(56 * scale))
    sub_size = max(16, int(32 * scale))
    body_size = max(14, int(26 * scale))

    title_font = _get_font("segoeui", title_size)
    sub_font = _get_font("consola", sub_size)
    body_font = _get_font("segoeui", body_size)

    title_text = getattr(scene, "visual_prompt", "") or getattr(scene, "scene_id", "Scene")
    narration = getattr(scene, "narration", "")
    scene_type = getattr(scene, "scene_type", SceneType.CONCEPT)

    # Top accent bar
    draw.rectangle([(0, 0), (width, max(4, int(8 * scale)))], fill=primary_color)

    center_x = width // 2
    top_y = int(height * 0.18)

    # Circular badge
    pulse_rad = max(16, int(28 * scale))
    draw.ellipse(
        [(center_x - pulse_rad, top_y - pulse_rad), (center_x + pulse_rad, top_y + pulse_rad)],
        outline=accent_color,
        width=max(2, int(3 * scale)),
    )

    tag_text = f"// {scene_type.upper()} //" if isinstance(scene_type, str) else f"// {scene_type.value.upper()} //"
    draw.text((center_x, top_y), tag_text, font=sub_font, fill=accent_color, anchor="mm")

    max_text_w = int(width * 0.85)
    title_lines = _wrap_text(title_text, title_font, max_text_w, draw)

    cur_y = int(height * 0.30)
    for line in title_lines[:3]:
        draw.text((center_x, cur_y), line, font=title_font, fill=primary_color, anchor="mm")
        cur_y += int(title_size * 1.3)

    cur_y += int(16 * scale)
    body_lines = _wrap_text(narration, body_font, max_text_w, draw)
    for line in body_lines[:4]:
        draw.text((center_x, cur_y), line, font=body_font, fill=text_color, anchor="mm")
        cur_y += int(body_size * 1.35)

    # Bottom progress bar
    pb_h = max(3, int(6 * scale))
    draw.rectangle(
        [(int(width * 0.1), height - int(height * 0.08)), (int(width * 0.9), height - int(height * 0.08) + pb_h)],
        fill=primary_color,
    )

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
            raise RuntimeError(f"FFmpeg animation rendering failed (exit {res.returncode})")
    finally:
        try:
            os.unlink(tmp_png)
        except OSError:
            pass

    return output_path
