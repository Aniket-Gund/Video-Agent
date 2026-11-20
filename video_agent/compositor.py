"""
video_agent.compositor - FFmpeg-based video composition engine.

Stitches scene clips with transitions, overlays subtitles, mixes audio,
and renders in both 9:16 (1080x1920) and 16:9 (1920x1080) formats.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from video_agent.models import SceneSpec, SceneType, VideoOptionSpec
from video_agent.visual.animations import render_animation_scene
from video_agent.visual.recorder import render_code_execution_scene

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ASPECT_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
}

_FORMAT_SUFFIX: Dict[str, str] = {
    "16:9": "horizontal_16x9",
    "9:16": "vertical_9x16",
}

_SUPPORTED_TRANSITIONS = {"fade", "wipeleft", "dissolve", "cut", "none"}

_VIDEO_CODEC_ARGS = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
_AUDIO_CODEC_ARGS = ["-c:a", "aac"]
_PIX_FMT_ARGS = ["-pix_fmt", "yuv420p"]

# Subtitle margins per aspect ratio (MarginV for ASS / bottom margin)
_SUBTITLE_MARGIN: Dict[str, int] = {
    "16:9": 40,
    "9:16": 120,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_ffmpeg() -> str:
    """Locate the ffmpeg executable on PATH.

    Returns
    -------
    str
        Absolute path to the ffmpeg binary.

    Raises
    ------
    FileNotFoundError
        If ffmpeg is not found on the system PATH.
    """
    path = shutil.which("ffmpeg")
    if path is None:
        raise FileNotFoundError(
            "ffmpeg not found on PATH. Install FFmpeg and ensure it is accessible."
        )
    return path


def _run_ffmpeg(args: List[str], *, desc: str = "ffmpeg") -> subprocess.CompletedProcess:
    """Execute an ffmpeg command with standard error handling.

    Parameters
    ----------
    args : list[str]
        Full argument list starting with the ffmpeg binary path.
    desc : str
        Human-readable description for error messages.

    Returns
    -------
    subprocess.CompletedProcess

    Raises
    ------
    RuntimeError
        If the ffmpeg process exits with a non-zero return code.
    """
    logger.debug("Running %s: %s", desc, " ".join(args))
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[-2000:]
        raise RuntimeError(
            f"{desc} failed (exit {result.returncode}):\n{stderr_tail}"
        )
    return result


def _get_video_duration(video_path: Path) -> float:
    """Probe a video file for its duration in seconds using ffprobe.

    Parameters
    ----------
    video_path : Path
        Path to the video file to probe.

    Returns
    -------
    float
        Duration in seconds.  Returns 0.0 on probe failure.
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        logger.warning("ffprobe not found; cannot probe duration of %s", video_path)
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as exc:
        logger.warning("ffprobe duration probe failed for %s: %s", video_path, exc)
    return 0.0


def _slugify(title: str) -> str:
    """Convert a title string to a filesystem-safe slug.

    Parameters
    ----------
    title : str
        The video title to slugify.

    Returns
    -------
    str
        Lowercase, underscore-separated slug string.
    """
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    slug = slug[:60].strip("_")
    return slug or "untitled"


# ---------------------------------------------------------------------------
# 1. render_scene_visual
# ---------------------------------------------------------------------------


def render_scene_visual(
    scene: SceneSpec,
    duration: float,
    aspect_ratio: str,
    theme: Dict[str, Any],
    output_dir: Path,
) -> Path:
    """Render a single scene's visual clip at the specified aspect ratio.

    Dispatches to the appropriate visual renderer based on ``scene.scene_type``:

    - ``SceneType.CODE_EXECUTION`` → ``render_code_execution_scene``
    - All others → ``render_animation_scene``

    Parameters
    ----------
    scene : SceneSpec
        The scene specification to render.
    duration : float
        Target clip duration in seconds (from the audio master clock).
    aspect_ratio : str
        Target aspect ratio string: ``"16:9"`` or ``"9:16"``.
    theme : dict
        Visual theme configuration (colors, fonts, etc.).
    output_dir : Path
        Directory in which to write the output MP4 clip.

    Returns
    -------
    Path
        Path to the generated scene clip MP4 file.

    Raises
    ------
    ValueError
        If ``aspect_ratio`` is not a supported value.
    """
    if aspect_ratio not in _ASPECT_DIMENSIONS:
        raise ValueError(
            f"Unsupported aspect ratio {aspect_ratio!r}. "
            f"Supported: {list(_ASPECT_DIMENSIONS.keys())}"
        )

    width, height = _ASPECT_DIMENSIONS[aspect_ratio]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ratio_tag = aspect_ratio.replace(":", "x")
    output_path = output_dir / f"{scene.scene_id}_{ratio_tag}.mp4"

    if scene.scene_type == SceneType.CODE_EXECUTION:
        return render_code_execution_scene(
            scene=scene,
            duration=duration,
            width=width,
            height=height,
            theme=theme,
            output_path=output_path,
        )
    else:
        return render_animation_scene(
            scene=scene,
            duration=duration,
            width=width,
            height=height,
            theme=theme,
            output_path=output_path,
        )


# ---------------------------------------------------------------------------
# 2. _concat_scenes_with_transitions
# ---------------------------------------------------------------------------


def _concat_scenes_with_transitions(
    scene_clips: List[Path],
    output_path: Path,
    transition: str = "fade",
    transition_duration: float = 0.5,
    subtitle_srt: Optional[Path] = None,
    aspect_ratio: str = "16:9",
    audio_path: Optional[Path] = None,
    scene_durations: Optional[List[float]] = None,
) -> Path:
    """Concatenate scene clips using ffmpeg xfade transitions.

    Builds an ffmpeg complex filtergraph that applies ``xfade`` filters
    between consecutive clips. If only a single clip is provided, it is
    copied directly to ``output_path``.
    """
    if not scene_clips:
        raise ValueError("scene_clips must contain at least one clip.")

    if transition not in _SUPPORTED_TRANSITIONS:
        logger.warning(
            "Unsupported transition %r; falling back to 'fade'.", transition
        )
        transition = "fade"

    ffmpeg = _find_ffmpeg()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Single clip: just re-encode / copy
    if len(scene_clips) == 1:
        cmd = [ffmpeg, "-y", "-i", str(scene_clips[0])]
        if audio_path is not None and Path(audio_path).exists():
            cmd.extend([
                "-i", str(audio_path),
                "-filter_complex", "[0:v]tpad=stop_mode=clone:stop_duration=1.0[vpad]",
                "-map", "[vpad]",
                "-map", "1:a",
                "-af", "apad=pad_dur=1.0",
                *_VIDEO_CODEC_ARGS,
                *_AUDIO_CODEC_ARGS,
                *_PIX_FMT_ARGS,
                "-shortest",
            ])
        else:
            cmd.extend([*_VIDEO_CODEC_ARGS, *_PIX_FMT_ARGS])
        cmd.append(str(output_path))
        _run_ffmpeg(cmd, desc="copy single clip")
        return output_path

    # Probe durations of each clip for xfade offset calculation if not provided
    if scene_durations and len(scene_durations) == len(scene_clips):
        durations = list(scene_durations)
    else:
        durations = []
        for clip in scene_clips:
            dur = _get_video_duration(clip)
            if dur <= 0:
                dur = 5.0  # fallback
                logger.warning("Could not probe duration for %s; assuming %.1fs", clip, dur)
            durations.append(dur)

    inputs: List[str] = []
    for clip in scene_clips:
        inputs.extend(["-i", str(clip)])

    has_audio = audio_path is not None and Path(audio_path).exists()
    if has_audio:
        inputs.extend(["-i", str(audio_path)])

    filter_parts: List[str] = []
    n = len(scene_clips)

    if transition in ("cut", "none") or transition_duration <= 0:
        filter_parts.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vcat]")
        prev_label = "[vcat]"
        cumulative_dur = sum(durations)
    else:
        # Pre-pad clips 0..n-2 by transition_duration so xfade preserves exact timeline lockstep with audio
        for i in range(n - 1):
            filter_parts.append(
                f"[{i}:v]tpad=stop_mode=clone:stop_duration={transition_duration:.2f}[v{i}_pad]"
            )

        cumulative_dur = durations[0]
        prev_label = "[v0_pad]"

        for i in range(1, n):
            offset = cumulative_dur
            out_label = f"[v{i}_out]"
            next_in = f"[v{i}_pad]" if i < n - 1 else f"[{i}:v]"
            filter_parts.append(
                f"{prev_label}{next_in}xfade=transition={transition}"
                f":duration={transition_duration:.2f}:offset={offset:.2f}{out_label}"
            )
            cumulative_dur = offset + durations[i]
            prev_label = out_label

    # Ensure video is padded to never cut off speech and provide 1.5s outro hold
    if has_audio:
        audio_dur = _get_video_duration(audio_path)
        if audio_dur <= 0 and scene_durations:
            audio_dur = sum(scene_durations)
        video_pad = max(0.0, audio_dur - cumulative_dur) + 1.5
        filter_parts.append(
            f"{prev_label}tpad=stop_mode=clone:stop_duration={video_pad:.2f}[vpad]"
        )
        prev_label = "[vpad]"

    if subtitle_srt is not None and Path(subtitle_srt).exists() and Path(subtitle_srt).stat().st_size > 0:
        margin_v = _SUBTITLE_MARGIN.get(aspect_ratio, 40)
        srt_escaped = str(subtitle_srt).replace("\\", "/").replace(":", "\\:")
        filter_parts.append(
            f"{prev_label}subtitles='{srt_escaped}':force_style="
            f"'FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"Outline=2,MarginV={margin_v},Alignment=2'[vout]"
        )
        prev_label = "[vout]"

    filtergraph = ";".join(filter_parts)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filtergraph,
        "-map", prev_label,
    ]

    if has_audio:
        cmd.extend([
            "-map", f"{n}:a",
            "-af", "apad=pad_dur=1.5",
            *_VIDEO_CODEC_ARGS,
            *_AUDIO_CODEC_ARGS,
            *_PIX_FMT_ARGS,
            "-shortest",
            str(output_path),
        ])
    else:
        cmd.extend([
            *_VIDEO_CODEC_ARGS,
            *_PIX_FMT_ARGS,
            "-an",
            str(output_path),
        ])

    _run_ffmpeg(cmd, desc="concat with xfade transitions")
    return output_path


# ---------------------------------------------------------------------------
# 3. _overlay_subtitles
# ---------------------------------------------------------------------------


def _merge_srt_files(
    srt_files: List[Path],
    scene_durations: List[float],
    output_path: Path,
) -> Path:
    """Merge per-scene SRT files into a single combined SRT with adjusted timestamps.

    Parameters
    ----------
    srt_files : list[Path]
        Per-scene SRT file paths (parallel with scene_durations).
    scene_durations : list[float]
        Duration of each scene in seconds.
    output_path : Path
        Destination path for the merged SRT file.

    Returns
    -------
    Path
        Path to the merged SRT file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    combined_entries: List[str] = []
    entry_index = 1
    time_offset = 0.0

    for idx, (srt_path, dur) in enumerate(zip(srt_files, scene_durations)):
        if srt_path is None or not Path(srt_path).exists():
            time_offset += dur
            continue

        content = Path(srt_path).read_text(encoding="utf-8", errors="replace")
        blocks = re.split(r"\n\s*\n", content.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            # Parse timestamp line: 00:00:01,000 --> 00:00:03,500
            ts_match = re.match(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
                lines[1].strip(),
            )
            if not ts_match:
                continue

            start = _srt_ts_to_seconds(ts_match.group(1)) + time_offset
            end = _srt_ts_to_seconds(ts_match.group(2)) + time_offset
            text = "\n".join(lines[2:])

            combined_entries.append(
                f"{entry_index}\n"
                f"{_seconds_to_srt_ts(start)} --> {_seconds_to_srt_ts(end)}\n"
                f"{text}"
            )
            entry_index += 1

        time_offset += dur

    output_path.write_text("\n\n".join(combined_entries) + "\n", encoding="utf-8")
    return output_path


def _srt_ts_to_seconds(ts: str) -> float:
    """Convert SRT timestamp ``HH:MM:SS,mmm`` to seconds."""
    parts = ts.replace(",", ".").split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def _seconds_to_srt_ts(seconds: float) -> str:
    """Convert seconds to SRT timestamp ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _overlay_subtitles(
    video_path: Path,
    srt_files: List[Path],
    scene_durations: List[float],
    output_path: Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """Burn subtitles into a video using the ffmpeg ``subtitles`` filter.

    Merges all per-scene SRT files into a single combined SRT (adjusting
    timestamps for sequential playback) and then uses the ffmpeg subtitles
    filter to render them at the bottom of the frame with appropriate margins.

    Parameters
    ----------
    video_path : Path
        Input video file to overlay subtitles onto.
    srt_files : list[Path]
        Per-scene SRT subtitle file paths.
    scene_durations : list[float]
        Duration of each scene in seconds (parallel with srt_files).
    output_path : Path
        Destination path for the subtitled video.
    aspect_ratio : str
        Aspect ratio for margin positioning (``"16:9"`` or ``"9:16"``).

    Returns
    -------
    Path
        Path to the output video with burned-in subtitles.

    Raises
    ------
    RuntimeError
        If the ffmpeg command fails.
    """
    ffmpeg = _find_ffmpeg()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter out None entries and check if we have any valid SRT files
    valid_srts = [p for p in srt_files if p is not None and Path(p).exists()]
    if not valid_srts:
        # No subtitles to overlay; copy video through
        logger.info("No valid SRT files found; skipping subtitle overlay.")
        shutil.copy2(str(video_path), str(output_path))
        return output_path

    # Merge SRT files into a single combined SRT
    with tempfile.TemporaryDirectory(prefix="va_subs_") as tmpdir:
        combined_srt = Path(tmpdir) / "combined.srt"
        _merge_srt_files(srt_files, scene_durations, combined_srt)

        if not combined_srt.exists() or combined_srt.stat().st_size == 0:
            logger.info("Combined SRT is empty; skipping subtitle overlay.")
            shutil.copy2(str(video_path), str(output_path))
            return output_path

        margin_v = _SUBTITLE_MARGIN.get(aspect_ratio, 40)

        # Escape path for ffmpeg subtitles filter (backslashes and colons)
        srt_escaped = str(combined_srt).replace("\\", "/").replace(":", "\\:")

        subtitle_filter = (
            f"subtitles='{srt_escaped}':force_style="
            f"'FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"Outline=2,MarginV={margin_v},Alignment=2'"
        )

        cmd = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", subtitle_filter,
            *_VIDEO_CODEC_ARGS,
            *_AUDIO_CODEC_ARGS,
            *_PIX_FMT_ARGS,
            str(output_path),
        ]

        _run_ffmpeg(cmd, desc="overlay subtitles")

    return output_path


# ---------------------------------------------------------------------------
# 4. _mix_audio
# ---------------------------------------------------------------------------


def _mix_audio(
    video_path: Path,
    audio_files: List[Path],
    scene_durations: List[float],
    output_path: Path,
) -> Path:
    """Mix voiceover audio files sequentially onto the video track.

    Concatenates the per-scene audio files with proper timing via an
    ffmpeg concat demuxer, then merges the combined audio with the video.

    Parameters
    ----------
    video_path : Path
        Input video file (may or may not already contain an audio stream).
    audio_files : list[Path]
        Per-scene voiceover audio file paths (parallel with scene_durations).
    scene_durations : list[float]
        Duration of each scene in seconds.
    output_path : Path
        Destination path for the final video with audio.

    Returns
    -------
    Path
        Path to the output video with mixed audio.

    Raises
    ------
    RuntimeError
        If the ffmpeg command fails.
    """
    ffmpeg = _find_ffmpeg()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter out None / missing audio files
    valid_audio: List[Tuple[Path, float]] = []
    for af, dur in zip(audio_files, scene_durations):
        if af is not None and Path(af).exists():
            valid_audio.append((Path(af), dur))

    if not valid_audio:
        logger.info("No valid audio files found; copying video without audio mix.")
        shutil.copy2(str(video_path), str(output_path))
        return output_path

    with tempfile.TemporaryDirectory(prefix="va_audio_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        if len(valid_audio) == 1:
            # Single audio file — merge directly with video
            combined_audio = valid_audio[0][0]
        else:
            # Concatenate audio files using ffmpeg concat demuxer
            concat_list = tmpdir_path / "concat.txt"
            lines = []
            for audio_path, _ in valid_audio:
                abs_posix = Path(audio_path).resolve().as_posix()
                lines.append(f"file '{abs_posix}'")
            concat_list.write_text("\n".join(lines), encoding="utf-8")

            combined_audio = tmpdir_path / "combined_audio.aac"
            _run_ffmpeg(
                [
                    ffmpeg, "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_list),
                    *_AUDIO_CODEC_ARGS,
                    str(combined_audio),
                ],
                desc="concatenate audio files",
            )

        # Merge combined audio with video, ensuring video never ends before audio
        v_dur = _get_video_duration(video_path)
        a_dur = _get_video_duration(combined_audio)
        if a_dur > v_dur and v_dur > 0:
            pad_dur = (a_dur - v_dur) + 1.0
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(combined_audio),
                "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={pad_dur:.2f}[vpad]",
                "-map", "[vpad]",
                "-map", "1:a:0",
                *_VIDEO_CODEC_ARGS,
                *_AUDIO_CODEC_ARGS,
                *_PIX_FMT_ARGS,
                "-af", "apad=pad_dur=1.0",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(combined_audio),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",  # no re-encode of video
                *_AUDIO_CODEC_ARGS,
                "-shortest",
                str(output_path),
            ]

        _run_ffmpeg(cmd, desc="mix audio onto video")

    return output_path


# ---------------------------------------------------------------------------
# 5. render_video_option (main entry point)
# ---------------------------------------------------------------------------


def render_video_option(
    option: VideoOptionSpec,
    output_dir: Path,
    formats: Optional[List[str]] = None,
    slug: Optional[str] = None,
) -> Dict[str, Path]:
    """Render a complete video option in the requested aspect-ratio formats.

    This is the main entry point for the composition engine.  For each
    requested format it:

    1. Renders each scene visual at the correct aspect ratio.
    2. Concatenates scenes with xfade transitions.
    3. Overlays burned-in subtitles.
    4. Mixes in voiceover audio.
    5. Writes the final output as
       ``<slug>_vertical_9x16.mp4`` or ``<slug>_horizontal_16x9.mp4``.

    Parameters
    ----------
    option : VideoOptionSpec
        The complete video option specification.
    output_dir : Path
        Directory in which to write all output files.
    formats : list[str] | None
        List of aspect-ratio strings to render.  Defaults to
        ``["9:16", "16:9"]``.

    Returns
    -------
    dict[str, Path]
        Mapping of format string (e.g. ``"9:16"``) to the rendered MP4 path.

    Raises
    ------
    ValueError
        If the option contains no scenes or an unsupported format is requested.
    RuntimeError
        If any ffmpeg or rendering step fails.
    """
    if formats is None:
        formats = ["9:16", "16:9"]

    if not option.scenes:
        raise ValueError("VideoOptionSpec contains no scenes to render.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if slug is None:
        base_title = option.title.split(":")[0] if ":" in option.title else option.title
        slug = _slugify(base_title)
    theme = option.visual_theme or {}
    results: Dict[str, Path] = {}

    for fmt in formats:
        if fmt not in _ASPECT_DIMENSIONS:
            raise ValueError(
                f"Unsupported format {fmt!r}. Supported: {list(_ASPECT_DIMENSIONS.keys())}"
            )

        logger.info("Rendering format %s for '%s'...", fmt, option.title)

        with tempfile.TemporaryDirectory(prefix=f"va_{slug[:20]}_{fmt.replace(':', 'x')}_") as tmpdir:
            tmpdir_path = Path(tmpdir)

            # ---- Step 1: Render each scene visual in parallel ----
            import concurrent.futures
            scenes_dir = tmpdir_path / "scenes"
            scenes_dir.mkdir(parents=True, exist_ok=True)

            def _render_one(sc):
                dur = sc.audio_duration if sc.audio_duration > 0 else 5.0
                c_path = render_scene_visual(
                    scene=sc,
                    duration=dur,
                    aspect_ratio=fmt,
                    theme=theme,
                    output_dir=scenes_dir,
                )
                return sc, c_path, dur

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(option.scenes), 4)) as pool:
                rendered_order = list(pool.map(_render_one, option.scenes))

            scene_clips = [item[1] for item in rendered_order]
            scene_durations = [item[2] for item in rendered_order]
            srt_files = [item[0].subtitles_srt for item in rendered_order]
            audio_files = [item[0].audio_file for item in rendered_order]

            # ---- Step 2: Merge subtitles and prepare audio ----
            combined_srt = tmpdir_path / "combined.srt"
            _merge_srt_files(srt_files, scene_durations, combined_srt)

            valid_audio = [
                (Path(af), dur)
                for af, dur in zip(audio_files, scene_durations)
                if af is not None and Path(af).exists()
            ]
            combined_audio = None
            if len(valid_audio) == 1:
                combined_audio = valid_audio[0][0]
            elif len(valid_audio) > 1:
                concat_list = tmpdir_path / "concat.txt"
                lines = [
                    f"file '{Path(af).resolve().as_posix()}'"
                    for af, _ in valid_audio
                ]
                concat_list.write_text("\n".join(lines), encoding="utf-8")
                combined_audio = tmpdir_path / "combined_audio.aac"
                _run_ffmpeg(
                    [
                        _find_ffmpeg(),
                        "-y",
                        "-f", "concat", "-safe", "0",
                        "-i", str(concat_list),
                        *_AUDIO_CODEC_ARGS,
                        str(combined_audio),
                    ],
                    desc="concatenate audio files",
                )

            # ---- Step 3: Single-pass render with transitions, subtitles, and audio ----
            suffix = _FORMAT_SUFFIX[fmt]
            final_name = f"{slug}_{suffix}.mp4"
            final_path = output_dir / final_name

            _concat_scenes_with_transitions(
                scene_clips=scene_clips,
                output_path=final_path,
                transition="fade",
                transition_duration=0.5,
                subtitle_srt=combined_srt,
                aspect_ratio=fmt,
                audio_path=combined_audio,
                scene_durations=scene_durations,
            )

            results[fmt] = final_path
            logger.info("Rendered %s -> %s", fmt, final_path)

    return results
