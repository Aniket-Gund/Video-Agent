---
name: video-agent
description: >-
  Autonomous Video Production and Editing Engine for creating professional animated videos
  and reels from scratch. Conducts automated topic research, generates multi-style scripts
  (Hacker Reel, Explainer, Walkthrough), synthesizes neural voiceovers (Edge-TTS), renders
  motion graphic animations (Pillow), captures terminal code execution demo recordings,
  and exports finished dual-format MP4 videos (9:16 vertical reel and 16:9 widescreen) with
  burned-in subtitles and xfade transitions.
---

# Video Agent - Professional Video & Reel Engine

Video Agent is an end-to-end automated video production system and interactive CLI designed to create high-production animated videos and viral reels from scratch. It handles topic research, multi-option scriptwriting, neural voice synthesis, procedural motion graphics, code execution screen recordings, audio ducking, and dual-format rendering.

## Workspace & Installation

- **Repository**: [https://github.com/Aniket-Gund/Video-Agent](https://github.com/Aniket-Gund/Video-Agent)
- **Main Entry Point**: `main.py`
- **Package Directory**: `video_agent/`
- **CLI Command**: `video-agent` or `python main.py`

### Register as an Antigravity Global Skill
To install this skill globally for your Antigravity or Gemini agent:
1. Copy this directory or `SKILL.md` into your Antigravity skills directory:
   - **Windows**: `%USERPROFILE%\.gemini\config\skills\video-agent\SKILL.md`
   - **macOS / Linux**: `~/.gemini/config/skills/video-agent/SKILL.md`
2. Ensure dependencies are installed via `pip install -e .` in this cloned repository.

---

## Core Capabilities & Pipeline Stages

1. **Environment Diagnostics (`video_agent.doctor`)**
   - Validates all runtimes and engines: FFmpeg 9.0.2+, FFprobe, Edge-TTS, Manim Community, Playwright Chromium, OpenCV, Pillow, MoviePy, Pydub, Rich, Questionary.
   - Run diagnostics anytime:
     ```bash
     video-agent --doctor
     # or
     python main.py --doctor
     ```

2. **Topic Research & Scriptwriting (`video_agent.research`, `video_agent.scriptwriter`)**
   - Ingests any technical or conceptual topic.
   - Decomposes into structured summary, key concepts, runnable code examples, and core takeaways.
   - Generates 3 distinct stylistic video variations:
     - **Hacker Reel (9:16)**: Fast-paced, high-tech matrix green & cyan aesthetic, energetic Christopher voice.
     - **Explainer (16:9)**: Methodical, clean royal blue architecture cards, professional Jenny voice.
     - **Walkthrough (16:9)**: Step-by-step tutorial, dark violet & orange gradient aesthetic, calm Guy voice.
   - Decomposes each option into 4 canonical scenes:
     - `INTRO`: Visual hook & title card
     - `CONCEPT`: Core architectural mechanism diagram
     - `CODE_EXECUTION`: Sandboxed syntax-highlighted code recording
     - `OUTRO`: Takeaway summary and call-to-action

3. **Neural Voiceover & Millisecond Subtitles (`video_agent.voiceover`)**
   - Synthesizes human-like neural audio via Microsoft Edge Neural TTS.
   - Measures exact audio duration $T_i$ for each scene, establishing the master visual clock.
   - Generates synchronized millisecond-accurate SRT/VTT subtitle tracks.

4. **Programmatic Visuals & Code Recording (`video_agent.visual`)**
   - `render_animation_scene`: Programmatic motion graphics, pulse animations, title cards, progress indicators via Pillow piped directly to FFmpeg.
   - `render_code_execution_scene`: Terminal execution recording with window chrome buttons, command prompt, syntax highlighting, and live typing animation.

5. **Compositing & Dual-Format Export (`video_agent.compositor`)**
   - Multi-scene stitching with smooth `xfade` transitions (fade, wipeleft, dissolve).
   - Burned-in subtitles positioned in mobile/cinematic safe zones (`subtitles` filter).
   - Audio mixing combining voiceover with video timing.
   - Dual-format delivery:
     - **Vertical Reel (9:16, 1080x1920)**: Formatted for Instagram Reels, YouTube Shorts, TikTok.
     - **Horizontal Widescreen (16:9, 1920x1080)**: Formatted for YouTube, LinkedIn, presentations.

6. **Delivery & Artifacts**
   - Rendered videos delivered to `output/` and copied to project root.
   - Generates structured run metadata: `research.json`, `script.json`, `metadata.json`.

---

## Quick CLI Usage

### 1. Interactive Mode
Prompts for topic (if not supplied), presents a styled comparison table of the 3 options, and lets you choose:
```bash
video-agent "Python Concurrency"
```

### 2. Pre-selected Style or Option
Generate a specific option directly:
```bash
# Select Option 1 (Hacker Reel)
video-agent "Docker Containers" --select 1

# Select by style name
video-agent "Kubernetes Ingress" --style "Explainer"
```

### 3. Aspect Ratio Selection
```bash
# Vertical 9:16 Reel Only (Shorts / Reels)
video-agent "Rust Memory Safety" --format 9:16 --select 1

# Horizontal 16:9 Only (Widescreen)
video-agent "System Architecture" --format 16:9 --select 2

# Both formats simultaneously (Default)
video-agent "FastAPI Microservices" --format both --select 1
```

### 4. Non-Interactive / Headless Automation
```bash
video-agent "AsyncIO Performance" --headless --output "output/asyncio"
```

---

## Programmatic Python API

```python
import asyncio
from pathlib import Path
from video_agent.research import research_topic
from video_agent.scriptwriter import generate_script_options
from video_agent.voiceover import synthesize_all_scenes, generate_all_subtitles
from video_agent.compositor import render_video_option

# 1. Research topic
research = research_topic("Python Decorators")

# 2. Generate 3 style options
options = generate_script_options(research)
selected = options[0]  # Hacker Reel

out_dir = Path("output/decorators")

# 3. Audio & Subtitles
asyncio.run(synthesize_all_scenes(selected, out_dir))
asyncio.run(generate_all_subtitles(selected, out_dir))

# 4. Render dual formats
videos = render_video_option(selected, out_dir, formats=["9:16", "16:9"])
print("Generated videos:", videos)
```
