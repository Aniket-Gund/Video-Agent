"""
Configuration constants for the Video Agent project.

Contains output paths, voice presets, and visual theme presets
for different video styles.
"""

from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Directory paths
# ---------------------------------------------------------------------------

PROJECT_DIR: Path = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR: Path = PROJECT_DIR / "output"

# ---------------------------------------------------------------------------
# Voice presets  (edge-tts voice names)
# ---------------------------------------------------------------------------

VOICE_PRESETS: Dict[str, str] = {
    "professional": "en-US-GuyNeural",
    "energetic": "en-US-JennyNeural",
    "calm": "en-US-AriaNeural",
    "friendly": "en-US-SaraNeural",
    "authoritative": "en-US-DavisNeural",
}

# ---------------------------------------------------------------------------
# Visual theme presets
# ---------------------------------------------------------------------------

VISUAL_THEMES: Dict[str, Dict[str, Any]] = {
    # ---- Hacker Reel ----
    "hacker_reel": {
        "background_color": "#0D1117",
        "accent_primary": "#00FF41",
        "accent_secondary": "#00CED1",
        "text_color": "#C9D1D9",
        "heading_color": "#00FF41",
        "font_family": "Courier New",
        "heading_font": "Courier New",
        "font_size_title": 64,
        "font_size_heading": 48,
        "font_size_body": 32,
        "font_size_code": 28,
        "font_size_caption": 24,
        "transition_type": "glitch",
        "transition_duration": 0.3,
        "color_palette": [
            "#00FF41",  # matrix green
            "#00CED1",  # dark cyan
            "#FF6EC7",  # neon pink
            "#FFFF00",  # yellow
            "#0D1117",  # dark bg
            "#161B22",  # panel bg
        ],
        "code_theme": "monokai",
        "border_style": "glow",
        "border_color": "#00FF41",
    },
    # ---- Explainer ----
    "explainer": {
        "background_color": "#FFFFFF",
        "accent_primary": "#2563EB",
        "accent_secondary": "#3B82F6",
        "text_color": "#1F2937",
        "heading_color": "#1E3A8A",
        "font_family": "Arial",
        "heading_font": "Helvetica",
        "font_size_title": 60,
        "font_size_heading": 44,
        "font_size_body": 30,
        "font_size_code": 26,
        "font_size_caption": 22,
        "transition_type": "fade",
        "transition_duration": 0.5,
        "color_palette": [
            "#2563EB",  # primary blue
            "#3B82F6",  # lighter blue
            "#10B981",  # green accent
            "#F59E0B",  # amber accent
            "#FFFFFF",  # white bg
            "#F3F4F6",  # light grey panel
        ],
        "code_theme": "github-light",
        "border_style": "solid",
        "border_color": "#2563EB",
    },
    # ---- Walkthrough ----
    "walkthrough": {
        "background_color": "#1A1A2E",
        "accent_primary": "#F97316",
        "accent_secondary": "#FB923C",
        "text_color": "#F5F5F5",
        "heading_color": "#F97316",
        "font_family": "Segoe UI",
        "heading_font": "Segoe UI",
        "font_size_title": 58,
        "font_size_heading": 42,
        "font_size_body": 30,
        "font_size_code": 26,
        "font_size_caption": 22,
        "transition_type": "slide",
        "transition_duration": 0.4,
        "color_palette": [
            "#F97316",  # orange primary
            "#FB923C",  # light orange
            "#A78BFA",  # violet accent
            "#34D399",  # teal accent
            "#1A1A2E",  # dark gradient start
            "#16213E",  # dark gradient end
        ],
        "gradient": {
            "start": "#1A1A2E",
            "end": "#16213E",
            "direction": "vertical",
        },
        "code_theme": "dracula",
        "border_style": "rounded",
        "border_color": "#F97316",
    },
}

# ---------------------------------------------------------------------------
# Convenience look-ups
# ---------------------------------------------------------------------------

STYLE_VOICE_MAP: Dict[str, str] = {
    "hacker_reel": VOICE_PRESETS["energetic"],
    "explainer": VOICE_PRESETS["professional"],
    "walkthrough": VOICE_PRESETS["calm"],
}

STYLE_NAMES = list(VISUAL_THEMES.keys())
