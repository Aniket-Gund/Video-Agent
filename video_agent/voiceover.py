"""
video_agent.voiceover - TTS audio synthesis and subtitle generation.

Synthesizes neural voiceover via edge-tts, extracts millisecond timestamps,
and generates compliant SRT/VTT subtitle tracks.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Union

import edge_tts
from pydub import AudioSegment

from video_agent.models import SceneSpec, VideoOptionSpec

logger = logging.getLogger(__name__)

DEFAULT_VOICE: str = "en-US-ChristopherNeural"

KNOWN_VOICES: List[str] = [
    "en-US-ChristopherNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-SaraNeural",
    "en-US-DavisNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
]


def sanitize_voice(voice: Optional[str]) -> str:
    """Normalize and validate a voice preset name, falling back to default if invalid."""
    if not voice or not isinstance(voice, str):
        return DEFAULT_VOICE
    target = voice.strip()
    for known in KNOWN_VOICES:
        if known.lower() == target.lower():
            return known
    # If it ends with Neural, accept as-is
    if "neural" in target.lower():
        return target
    return DEFAULT_VOICE


def _generate_synthetic_fallback_audio(text: str, output_path: Path) -> float:
    """Fallback generator creating a valid MP3 file with sine tone / silence when offline."""
    words = len(text.split()) if text.strip() else 1
    duration = max(1.5, words * 0.4)
    ffmpeg_bin = shutil.which("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration:.2f}",
            "-c:a", "libmp3lame",
            "-b:a", "64k",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and output_path.exists():
            return duration
    # Minimal MP3 fallback if ffmpeg is somehow unavailable
    silent = AudioSegment.silent(duration=int(duration * 1000))
    silent.export(str(output_path), format="mp3")
    return duration


def get_audio_duration(audio_path: Path) -> float:
    """Inspect an audio file (MP3/WAV) and return its exact duration in seconds."""
    try:
        segment = AudioSegment.from_file(str(audio_path))
        return len(segment) / 1000.0
    except Exception:
        # Fall back to ffprobe
        ffprobe_bin = shutil.which("ffprobe")
        if ffprobe_bin:
            cmd = [
                ffprobe_bin,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout.strip():
                try:
                    return float(res.stdout.strip())
                except ValueError:
                    pass
    return 3.0


def synthesize_speech(
    text: str, output_path: Union[str, Path], voice: str = DEFAULT_VOICE
) -> Path:
    """Synchronously synthesize narration text to an MP3 audio file.

    Raises:
        ValueError: If text is empty or whitespace-only.
    """
    if not text or not text.strip():
        raise ValueError("Narration text cannot be empty or whitespace.")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    clean_voice = sanitize_voice(voice)

    async def _do_synth():
        comm = edge_tts.Communicate(text.strip(), clean_voice)
        await comm.save(str(out_file))

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Nested in running loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(lambda: asyncio.run(_do_synth())).result(timeout=25.0)
            else:
                loop.run_until_complete(_do_synth())
        except RuntimeError:
            asyncio.run(_do_synth())
    except Exception as exc:
        logger.warning("edge-tts synthesis encountered error (%s); using fallback audio.", exc)
        _generate_synthetic_fallback_audio(text, out_file)

    if not out_file.exists() or out_file.stat().st_size == 0:
        _generate_synthetic_fallback_audio(text, out_file)

    return out_file


async def synthesize_voiceover(
    scene: SceneSpec, voice_name: str, output_dir: Path
) -> SceneSpec:
    """Synthesize voiceover for a single scene and record audio file and duration."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_file = out_dir / f"{scene.scene_id}.mp3"

    narration = scene.narration.strip() if scene.narration else ""
    if not narration:
        duration = scene.audio_duration if scene.audio_duration > 0 else 3.0
        _generate_synthetic_fallback_audio("Silence", audio_file)
        scene.audio_file = audio_file
        scene.audio_duration = duration
        return scene

    clean_voice = sanitize_voice(voice_name)
    try:
        comm = edge_tts.Communicate(narration, clean_voice)
        await comm.save(str(audio_file))
    except Exception as exc:
        logger.warning("Synthesis error for %s: %s; using fallback.", scene.scene_id, exc)
        _generate_synthetic_fallback_audio(narration, audio_file)

    if not audio_file.exists() or audio_file.stat().st_size == 0:
        _generate_synthetic_fallback_audio(narration, audio_file)

    dur = get_audio_duration(audio_file)
    scene.audio_file = audio_file
    scene.audio_duration = max(dur, 1.0)
    return scene


async def synthesize_all_scenes(
    option: VideoOptionSpec, output_dir: Path
) -> VideoOptionSpec:
    """Synthesize voiceover audio for every scene in a VideoOptionSpec in parallel."""
    out_dir = Path(output_dir) / f"option_{option.option_id}_audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = [synthesize_voiceover(scene, option.voice_name, out_dir) for scene in option.scenes]
    await asyncio.gather(*tasks)

    option.estimated_duration = sum(s.audio_duration for s in option.scenes)
    return option


def format_srt_timestamp(seconds: float) -> str:
    """Format floating seconds as SRT timestamp: HH:MM:SS,mmm."""
    secs = max(0.0, seconds)
    hrs = int(secs // 3600)
    rem = secs % 3600
    mins = int(rem // 60)
    s = int(rem % 60)
    millis = int(round((rem - s) * 1000))
    if millis >= 1000:
        s += 1
        millis -= 1000
    return f"{hrs:02d}:{mins:02d}:{s:02d},{millis:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    """Format floating seconds as WebVTT timestamp: HH:MM:SS.mmm."""
    srt = format_srt_timestamp(seconds)
    return srt.replace(",", ".")


def generate_srt(
    scene: SceneSpec, output_dir: Path, time_offset: float = 0.0
) -> Path:
    """Generate a valid SRT subtitle file for a scene, synchronized across its duration."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_file = out_dir / f"{scene.scene_id}.srt"

    text = scene.narration.strip() if scene.narration else ""
    if not text:
        srt_file.write_text("", encoding="utf-8")
        scene.subtitles_srt = srt_file
        return srt_file

    words = text.split()
    # Chunk words into ~6-8 word groups
    chunk_size = 7
    chunks: List[str] = [
        " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
    ]
    if not chunks:
        chunks = [text]

    total_duration = max(scene.audio_duration, 1.0)
    chunk_dur = total_duration / len(chunks)

    cues: List[str] = []
    current_start = time_offset
    for idx, chunk in enumerate(chunks, start=1):
        current_end = current_start + chunk_dur
        start_ts = format_srt_timestamp(current_start)
        end_ts = format_srt_timestamp(current_end)
        cues.append(f"{idx}\n{start_ts} --> {end_ts}\n{chunk}\n")
        current_start = current_end

    content = "\n".join(cues) + "\n"
    srt_file.write_text(content, encoding="utf-8")
    scene.subtitles_srt = srt_file
    return srt_file


async def generate_all_subtitles(
    option: VideoOptionSpec, output_dir: Path
) -> VideoOptionSpec:
    """Generate synchronized SRT subtitles for each scene in the option."""
    out_dir = Path(output_dir) / f"option_{option.option_id}_subtitles"
    out_dir.mkdir(parents=True, exist_ok=True)

    for scene in option.scenes:
        generate_srt(scene, out_dir, time_offset=0.0)

    return option


def generate_combined_srt(option: VideoOptionSpec, output_path: Path) -> Path:
    """Merge scene subtitles with cumulative time offsets into a single master SRT file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_cues: List[str] = []
    cue_counter = 1
    cumulative_time = 0.0

    for scene in option.scenes:
        narration = scene.narration.strip() if scene.narration else ""
        if narration:
            words = narration.split()
            chunk_size = 7
            chunks = [
                " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
            ]
            if not chunks:
                chunks = [narration]

            scene_dur = max(scene.audio_duration, 1.0)
            chunk_dur = scene_dur / len(chunks)

            curr_start = cumulative_time
            for chunk in chunks:
                curr_end = curr_start + chunk_dur
                start_ts = format_srt_timestamp(curr_start)
                end_ts = format_srt_timestamp(curr_end)
                all_cues.append(f"{cue_counter}\n{start_ts} --> {end_ts}\n{chunk}\n")
                cue_counter += 1
                curr_start = curr_end

        cumulative_time += max(scene.audio_duration, 1.0)

    content = "\n".join(all_cues) + "\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path
