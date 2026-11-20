"""
video_agent.models - Core data models for the Video Agent pipeline.

Defines the structured types used across planning, visual rendering,
audio synthesis, and final composition stages. Provides both legacy
dataclass models and Pydantic-based models for the full pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ===========================================================================
# Scene type enumeration (str, Enum for Pydantic compat)
# ===========================================================================


class SceneType(str, Enum):
    """Enumeration of supported scene types in the video pipeline."""
    INTRO = "intro"
    CONCEPT = "concept"
    CODE_EXECUTION = "code_execution"
    OUTRO = "outro"


# ===========================================================================
# Legacy dataclass-based models (Milestone 1-3 compatibility)
# ===========================================================================


@dataclass
class SceneSpec_DC:
    """
    Legacy dataclass specification for a single scene (Milestone 1-3).

    Attributes:
        scene_type:    The category of scene (intro, concept, code, outro).
        title:         Display title for the scene.
        narration:     Voiceover script text for TTS synthesis.
        visual_prompt: Description of what the visual should depict.
        code_snippet:  Source code to display (for CODE scenes).
        code_language: Programming language of the code_snippet.
        key_points:    Bullet points for CONCEPT scenes.
        duration:      Suggested duration in seconds.
        metadata:      Arbitrary extra data for extensibility.
    """
    scene_type: SceneType
    title: str = ""
    narration: str = ""
    visual_prompt: str = ""
    code_snippet: Optional[str] = None
    code_language: str = "python"
    key_points: List[str] = field(default_factory=list)
    duration: float = 5.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoProject:
    """
    Top-level container for a complete video project.

    Attributes:
        title:       Project title.
        description: Brief description of the video content.
        scenes:      Ordered list of scene specifications.
        theme:       Visual theme configuration (colors, fonts, etc.).
        output_dir:  Directory for rendered output files.
        fps:         Target frames per second.
        width:       Video width in pixels.
        height:      Video height in pixels.
    """
    title: str = "Untitled Video"
    description: str = ""
    scenes: List[SceneSpec_DC] = field(default_factory=list)
    theme: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#1a1a2e",
        "text_color": "#e0e0e0",
        "accent_color": "#0f3460",
        "highlight_color": "#e94560",
        "font_family": "Consolas",
        "gradient_start": "#1a1a2e",
        "gradient_end": "#16213e",
    })
    output_dir: Path = field(default_factory=lambda: Path("output"))
    fps: int = 30
    width: int = 1920
    height: int = 1080


# ===========================================================================
# Pydantic-based models (Milestone 2+ pipeline contracts)
# ===========================================================================


class CodeSnippetSpec(BaseModel):
    """Specification for a code example extracted during research."""
    language: str = "python"
    code: str
    description: Optional[str] = None
    command: Optional[str] = None


class ResearchResult(BaseModel):
    """Structured research output from the topic research module."""
    topic: str
    title: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    code_snippets: List[CodeSnippetSpec] = Field(default_factory=list)
    code_examples: List[Dict[str, Any]] = Field(default_factory=list)
    takeaways: List[str] = Field(default_factory=list)
    takeaway: Optional[str] = None
    references: List[str] = Field(default_factory=list)


class SceneSpec(BaseModel):
    """Pydantic specification for a single scene in the video pipeline."""
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
    """Full specification for a single video style option."""
    option_id: int
    style_name: str
    title: str
    tagline: str
    voice_name: str
    scenes: List[SceneSpec]
    estimated_duration: float
    visual_theme: Dict[str, Any]
