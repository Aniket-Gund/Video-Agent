"""
video_agent.scriptwriter - Multi-option script generator.

Produces distinct stylistic script variations (Hacker Reel, Explainer, Walkthrough)
from structured research, decomposing each option into timed scenes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from video_agent.models import ResearchResult, SceneSpec, SceneType, VideoOptionSpec


AVAILABLE_STYLES: List[str] = ["Hacker Reel", "Explainer", "Walkthrough"]

STYLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "Hacker Reel": {
        "voice": "en-US-ChristopherNeural",
        "tagline": "Unlock extreme speed in 60 seconds",
        "theme": {
            "primary_color": "#00FF41",
            "background_color": "#0D1117",
            "font_family": "Consolas",
            "accent_color": "#00CED1",
            "aspect_ratio": "9:16",
        },
        "hook_prefix": "Discover high performance with",
        "concept_prefix": "At its core,",
        "demo_prefix": "Watch how we execute with",
        "outro_prefix": "Follow for daily patterns on",
    },
    "Explainer": {
        "voice": "en-US-JennyNeural",
        "tagline": "Clear, visual, architectural breakdown",
        "theme": {
            "primary_color": "#2563EB",
            "background_color": "#FFFFFF",
            "font_family": "Arial",
            "accent_color": "#3B82F6",
            "aspect_ratio": "16:9",
        },
        "hook_prefix": "Here is an architectural breakdown of",
        "concept_prefix": "At its core,",
        "demo_prefix": "Examine this practical implementation of",
        "outro_prefix": "Build scalable systems with",
    },
    "Walkthrough": {
        "voice": "en-US-GuyNeural",
        "tagline": "Step-by-step practical implementation tutorial",
        "theme": {
            "primary_color": "#F97316",
            "background_color": "#1A1A2E",
            "font_family": "Segoe UI",
            "accent_color": "#FB923C",
            "aspect_ratio": "16:9",
        },
        "hook_prefix": "Step by step walkthrough of",
        "concept_prefix": "Key foundation of",
        "demo_prefix": "Run the demo script for",
        "outro_prefix": "That concludes our quickstart for",
    },
}


def get_available_styles() -> List[str]:
    """Return the list of supported style names."""
    return list(AVAILABLE_STYLES)


def resolve_style_preset(style_name: str) -> str:
    """Resolve a user-supplied style name (case-insensitive) to a canonical style name.

    Falls back to 'Hacker Reel' if the style is unrecognized.
    """
    if not style_name:
        return "Hacker Reel"
    target = style_name.strip().lower()
    for canonical in AVAILABLE_STYLES:
        if canonical.lower() == target:
            return canonical
    return "Hacker Reel"


def generate_script_options(
    arg1: Any,
    arg2: Any = None,
    num_options: int = 3,
) -> List[VideoOptionSpec]:
    """Generate multiple distinct stylistic script variations from research.

    Supports both signatures:
        generate_script_options(research: ResearchResult, num_options: int = 3)
        generate_script_options(topic: str, research: ResearchResult, num_options: int = 3)
    """
    if isinstance(arg1, str) and arg2 is not None:
        clean_topic = arg1
        research = arg2
    elif hasattr(arg1, "topic"):
        research = arg1
        clean_topic = research.topic
        if isinstance(arg2, int):
            num_options = arg2
    else:
        research = arg2 if arg2 is not None else arg1
        clean_topic = getattr(research, "topic", str(arg1))
    snippet_code = ""
    if research.code_snippets:
        snippet_code = research.code_snippets[0].code
    elif research.code_examples:
        snippet_code = research.code_examples[0].get("code", "")
    if not snippet_code:
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", clean_topic.lower())
        snippet_code = (
            f"# {clean_topic} Quickstart\n"
            f"def demo_{safe_name}():\n"
            f"    print('Running {clean_topic} benchmark...')\n"
            f"    return True\n\n"
            f"if __name__ == '__main__':\n"
            f"    demo_{safe_name}()"
        )

    options: List[VideoOptionSpec] = []
    styles_to_use = AVAILABLE_STYLES[: max(1, min(num_options, len(AVAILABLE_STYLES)))]

    for idx, style_name in enumerate(styles_to_use, start=1):
        cfg = STYLE_CONFIGS[style_name]
        theme = dict(cfg["theme"])
        voice = cfg["voice"]
        tagline = cfg["tagline"]

        # 4 Canonical scenes
        # Scene 1: INTRO
        intro_narration = f"{cfg['hook_prefix']} {clean_topic}."
        scene1 = SceneSpec(
            scene_id=f"scene_{idx:03d}_intro",
            scene_type=SceneType.INTRO,
            narration=intro_narration,
            visual_prompt=f"Title card displaying {clean_topic} in {style_name} aesthetic",
            audio_duration=3.5,
        )

        # Scene 2: CONCEPT
        key_pt = research.key_points[0] if research.key_points else clean_topic
        concept_body = key_pt
        if ":" in concept_body:
            concept_body = concept_body.split(":", 1)[1].strip()
        if "." in concept_body:
            concept_body = concept_body.split(".")[0].strip()
        concept_words = " ".join(concept_body.split()[:7])
        concept_narration = f"{cfg['concept_prefix']} {clean_topic} enables {concept_words}."
        scene2 = SceneSpec(
            scene_id=f"scene_{idx:03d}_concept",
            scene_type=SceneType.CONCEPT,
            narration=concept_narration,
            visual_prompt=f"Educational diagram demonstrating core mechanisms of {clean_topic}",
            audio_duration=4.5,
        )

        # Scene 3: CODE_EXECUTION
        demo_narration = f"{cfg['demo_prefix']} {clean_topic} in real time."
        scene3 = SceneSpec(
            scene_id=f"scene_{idx:03d}_demo",
            scene_type=SceneType.CODE_EXECUTION,
            narration=demo_narration,
            visual_prompt=f"Terminal recording executing code snippet for {clean_topic}",
            code_snippet=snippet_code,
            command="python demo.py",
            audio_duration=5.0,
        )

        # Scene 4: OUTRO
        takeaway = research.takeaways[0] if research.takeaways else (research.takeaway or clean_topic)
        takeaway_body = takeaway.split(".")[0].strip() if takeaway else clean_topic
        outro_narration = f"{cfg['outro_prefix']} {takeaway_body}. Connect with Aniket Gund and follow @analysis_with_aniket for more deep-dive architectures."
        scene4 = SceneSpec(
            scene_id=f"scene_{idx:03d}_outro",
            scene_type=SceneType.OUTRO,
            narration=outro_narration,
            visual_prompt=f"Summary takeaway screen and call-to-action for {clean_topic}",
            audio_duration=4.5,
        )

        scenes = [scene1, scene2, scene3, scene4]
        total_duration = sum(s.audio_duration for s in scenes)

        title = f"{clean_topic}: {style_name} Edition"
        option = VideoOptionSpec(
            option_id=idx,
            style_name=style_name,
            title=title,
            tagline=tagline,
            voice_name=voice,
            scenes=scenes,
            estimated_duration=total_duration,
            visual_theme=theme,
        )
        options.append(option)

    return options
