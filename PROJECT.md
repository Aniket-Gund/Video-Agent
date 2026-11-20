# Project: Video Agent

## Architecture
Automated end-to-end Video Agent pipeline and interactive CLI producing animated videos and professional reels from scratch with topic research, scriptwriting, voiceover, animations, code execution recordings, and selectable video options.

```
+-----------------------------------------------------------------------------------+
|                                  Video Agent CLI                                   |
|                (Interactive selection, multi-option preview, flags)               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        Topic Research & Script Generation                         |
|   - Ingests topic -> conducts research (knowledge base / Gemini / Web)            |
|   - Generates 3 distinct stylistic options (Hacker Reel, Explainer, Walkthrough)   |
|   - Decomposes into timed scenes (Hook, Concept, Code Demo, Conclusion)           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        Voiceover & Subtitle Synchronization                       |
|   - Edge-TTS neural voiceover synthesis (multi-voice presets)                     |
|   - Millisecond subtitle generation (SRT/VTT) via word/sentence boundaries        |
|   - Master clock calibration: audio duration Ti determines visual scene duration  |
+-----------------------------------------------------------------------------------+
                                          |
                     +--------------------+--------------------+
                     |                                         |
                     v                                         v
+---------------------------------------+ +-----------------------------------------+
|        Programmatic Animations        | |   Code Execution / Terminal Recording   |
|  - Title cards & motion graphics      | |  - Sandboxed execution of real scripts  |
|  - Procedural diagrams & counters     | |  - Syntax highlighting (Pygments/Rich)  |
|  - Pillow / Manim / Canvas rendering  | |  - Headless Playwright Chromium capture |
+---------------------------------------+ +-----------------------------------------+
                     |                                         |
                     +--------------------+--------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       Compositor & Dual-Format Exporter                           |
|   - FFmpeg 9.0.2 filtergraph engine                                               |
|   - Scene transitions (xfade: fade, wipeleft, slideleft, dissolve)                |
|   - Audio ducking (sidechaincompress) balancing voiceover & background music      |
|   - Dual-format rendering:                                                        |
|       * Vertical Reel: 9:16 aspect ratio (1080x1920) with blurred ambient padding  |
|       * Standard Video: 16:9 aspect ratio (1920x1080) widescreen                  |
|   - Subtitle burning (libass / subtitles filter) with safe-zone positioning       |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       Output Delivery & Project Storage                           |
|   - Output MP4 files delivered to project directory and output/ folder            |
|   - Complete metadata artifacts: research.json, script.json, metadata.json        |
+-----------------------------------------------------------------------------------+
```

## Feature Inventory
Every feature from the Survey phase appears here with its assigned milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Global Tooling Setup & Verification | Install missing global packages (`manim`, `opencv-python`, `questionary`, `pyttsx3`, `@remotion/cli`, `vhs`, `ttyd`) and verify CLI tools (`ffmpeg`, `ffprobe`, `edge-tts`, `playwright`, `manim`) | M1 | R1, AC-1 |
| 2 | Environment Doctor & Diagnostics | CLI diagnostic command (`video-agent doctor`) verifying all runtimes, codecs, and engines | M1 | R1, AC-1 |
| 3 | Topic Research & Knowledge Engine | Ingests topic, produces structured research summary with key points, code examples, and takeaway | M2 | R2, AC-2 |
| 4 | Multi-Option Script Generation | Generates 3 distinct stylistic options with scene breakdowns (Hook, Concept, Code Demo, Conclusion) | M2 | R2, R3, AC-2 |
| 5 | Voiceover Synthesis & Timing Sync | Synthesizes neural voiceover via `edge-tts`, extracts millisecond word/sentence timestamps for subtitles | M2 | R2, AC-3 |
| 6 | Subtitle Generator & Master Clock | Generates SRT/VTT subtitles and establishes scene audio duration as visual master clock | M2 | R2, AC-3 |
| 7 | Programmatic Animation Engine | Renders motion graphics, animated title cards, diagrams, and counters via Pillow/Pygments/Playwright/Manim | M3 | R2, AC-4 |
| 8 | Terminal Code Execution Recorder | Sandboxed script execution, Pygments/Rich syntax highlighting, and headless Playwright video recording | M3 | R2, AC-4 |
| 9 | Dual-Format Composition Engine | FFmpeg filtergraph pipeline stitching scenes with xfade transitions and audio ducking | M4 | R2, AC-5 |
| 10 | Vertical Reel Formatter (9:16) | Renders 1080x1920 vertical video with blurred ambient background fill and mobile safe zones | M4 | R2, AC-5 |
| 11 | Horizontal Video Formatter (16:9) | Renders 1920x1080 widescreen video with cinematic layout and bottom third subtitles | M4 | R2, AC-5 |
| 12 | Interactive CLI & Multi-Option UI | Interactive terminal CLI presenting styled options with script previews and parameter details | M5 | R3, AC-6 |
| 13 | Interactive & Non-Interactive Selection | Selection prompt with support for `--select`, `--style`, and automated headless non-interactive fallback | M5 | R3, AC-6 |
| 14 | Project Delivery & Metadata Storage | Saves final rendered MP4 files into project directory and outputs run artifacts (research.json, script.json) | M5 | R3, AC-7 |
| 15 | E2E Acceptance & Quality Verification | Full end-to-end execution verifying all acceptance criteria and adversarial edge-case hardening | M6 | AC-1 to AC-7 |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Global Tooling Setup & Verification | Global installation of missing packages, CLI verification of all engines, and `doctor` module | none | IN_PROGRESS (7091b621-87bd-4ef8-aab2-b9cb9fce3cc7) |
| 2 | Research, Scriptwriting & Voiceover Sync | Research module, Pydantic schemas, script generator, edge-tts voiceover & SRT sync | M1 | PLANNED |
| 3 | Visual Production: Animations & Code Recording | Programmatic animations (title cards, diagrams) and headless Playwright code execution recorder | M1 | PLANNED |
| 4 | Video Composition & Dual-Format Rendering | FFmpeg composition engine, xfade transitions, audio ducking, 9:16 and 16:9 rendering | M2, M3 | PLANNED |
| 5 | Interactive CLI, Option Selection & Delivery | Interactive CLI, multi-option preview, selection prompt, output delivery to project directory | M4 | PLANNED |
| 6 | E2E Integration & Verification (Final Milestone) | Pass 100% of E2E test suite (Tiers 1-4) published by E2E track, then Tier 5 adversarial hardening | M5 | PLANNED |

## Interface Contracts

### M1 ↔ Pipeline Modules (`video_agent.doctor`)
- `check_environment() -> Dict[str, ToolStatus]`: Returns status of `ffmpeg`, `ffprobe`, `edge-tts`, `playwright`, `manim`, `python`, `node`.
- `ensure_dependencies() -> bool`: Verifies all critical dependencies are ready.

### M2 (Research & Script) ↔ M3/M4 (Visuals & Composition)
- Data Models (`video_agent.models`):
  ```python
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
  ```

### M3 (Visuals) ↔ M4 (Compositor)
- Visual generator contract:
  - `render_scene_visual(scene: SceneSpec, duration: float, aspect_ratio: str, output_path: Path) -> Path`
  - Guarantees valid MP4 video at requested duration and framerate (30fps), matching the audio master clock.

### M4 (Compositor) ↔ M5 (CLI & Delivery)
- Compositor contract:
  - `render_video_option(option: VideoOptionSpec, output_dir: Path, formats: List[str] = ["9:16", "16:9"]) -> Dict[str, Path]`
  - Returns paths to generated video files:
    - Vertical: `<output_dir>/<slug>_vertical_9x16.mp4` (1080x1920)
    - Horizontal: `<output_dir>/<slug>_horizontal_16x9.mp4` (1920x1080)
    - Also copies them into the project root directory.

## Code Layout
```
c:\Users\anike\Desktop\Video Agent\
├── video_agent/
│   ├── __init__.py
│   ├── cli.py             # Click/Rich interactive CLI, multi-option preview & selection
│   ├── config.py          # Configuration constants, paths, default voices and themes
│   ├── doctor.py          # Environment diagnostics and tool verifications
│   ├── models.py          # Pydantic data schemas (ScriptSpec, SceneSpec, OptionSpec)
│   ├── research.py        # Topic research, knowledge base, outline extraction
│   ├── scriptwriter.py    # Script generator and multi-style option variations
│   ├── voiceover.py       # Edge-TTS voiceover synthesis and SRT subtitle generator
│   ├── visual/
│   │   ├── __init__.py
│   │   ├── animations.py  # Programmatic motion graphics, title cards, diagrams
│   │   └── recorder.py    # Headless Playwright code execution / terminal recorder
│   └── compositor.py      # FFmpeg filtergraph engine, transitions, ducking, dual-format
├── main.py                # Root CLI entry point
├── tests/
│   ├── conftest.py
│   ├── test_r1_environment.py
│   ├── test_r2_pipeline.py
│   ├── test_r3_cli.py
│   └── test_e2e_pipeline.py
├── output/                # Default generated media and artifacts
└── .agents/teamwork/      # Teamwork metadata
```
