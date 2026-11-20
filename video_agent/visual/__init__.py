"""
video_agent.visual - Visual rendering package for the Video Agent pipeline.

Provides programmatic animation rendering (Pillow-based) and code execution
screen recording (Pygments + Pillow) modules that produce MP4 video files.
"""

from video_agent.visual.animations import render_animation_scene
from video_agent.visual.recorder import render_code_execution_scene

__all__ = [
    "render_animation_scene",
    "render_code_execution_scene",
]
