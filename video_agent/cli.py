"""
video_agent.cli - Interactive command-line interface for Video Agent.

Supports interactive option preview and selection with Rich tables and Questionary,
as well as headless non-interactive automation, format targeting, diagnostics,
and dual artifact delivery.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from video_agent import __version__
from video_agent.compositor import render_video_option
from video_agent.doctor import diagnose_cli
from video_agent.models import ResearchResult, VideoOptionSpec
from video_agent.research import research_topic, validate_topic
from video_agent.scriptwriter import (
    AVAILABLE_STYLES,
    generate_script_options,
    get_available_styles,
    resolve_style_preset,
)
from video_agent.voiceover import generate_all_subtitles, synthesize_all_scenes

console = Console()

VALID_FORMATS: List[str] = ["9:16", "16:9", "both", "vertical", "horizontal"]


def sanitize_slug(text: str) -> str:
    """Sanitize topic text into a cross-platform safe filename slug."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", text)
    slug = re.sub(r"[\s\-_]+", "_", cleaned).strip("_").lower()
    return slug[:60] if slug else "video"


def display_banner() -> None:
    """Display styled ASCII / Rich banner for Video Agent."""
    banner_text = (
        "[bold cyan]====================================================[/bold cyan]\n"
        "[bold green]        VIDEO AGENT - AI Video Engine & Editor       [/bold green]\n"
        f"[dim]                   Version {__version__}                    [/dim]\n"
        "[bold cyan]====================================================[/bold cyan]"
    )
    console.print(Panel(banner_text, border_style="cyan"))


def display_research_summary(research: ResearchResult) -> None:
    """Render topic research summary in a styled Rich panel."""
    points_md = "\n".join(f"• {pt}" for pt in research.key_points)
    content = (
        f"[bold cyan]Topic:[/bold cyan] {research.topic}\n\n"
        f"[bold]Summary:[/bold]\n{research.summary}\n\n"
        f"[bold]Key Concepts:[/bold]\n{points_md}\n\n"
        f"[bold]Takeaway:[/bold] {research.takeaway or (research.takeaways[0] if research.takeaways else '')}"
    )
    console.print(Panel(content, title="[bold]Topic Research Summary[/bold]", border_style="blue"))


def display_options_table(options: List[VideoOptionSpec]) -> None:
    """Display generated video options in a rich comparative table."""
    table = Table(title="Generated Video Style Options", border_style="green")
    table.add_column("Option #", justify="center", style="bold cyan")
    table.add_column("Style", style="bold magenta")
    table.add_column("Title", style="white")
    table.add_column("Tagline", style="dim")
    table.add_column("Voice", style="yellow")
    table.add_column("Est. Duration", justify="right", style="green")

    for opt in options:
        table.add_row(
            f"Option {opt.option_id}",
            opt.style_name,
            opt.title,
            opt.tagline,
            opt.voice_name,
            f"{opt.estimated_duration:.1f}s",
        )

    console.print(table)


@click.command(name="video-agent", context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("topic_arg", required=False, default="")
@click.option(
    "--topic",
    "-t",
    "topic_opt",
    type=str,
    default=None,
    help="Topic for video generation.",
)
@click.option(
    "--select",
    "-s",
    "select_opt",
    type=str,
    default=None,
    help="Pre-select option number (1, 2, or 3).",
)
@click.option(
    "--style",
    "style_opt",
    type=str,
    default=None,
    help="Select video style by name ('Hacker Reel', 'Explainer', 'Walkthrough').",
)
@click.option(
    "--format",
    "-f",
    "format_opt",
    type=str,
    default="both",
    help="Video format / aspect ratio: '9:16', '16:9', 'both', 'vertical', 'horizontal'.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    default="output",
    help="Target output directory for videos and artifacts.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    help="Non-interactive execution mode (defaults to Option 1).",
)
@click.option(
    "--interactive",
    is_flag=True,
    default=False,
    help="Enable interactive selection prompt.",
)
@click.option(
    "--doctor",
    is_flag=True,
    default=False,
    help="Run environment health checks and diagnostics.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing output files.",
)
@click.version_option(version=__version__, message="%(prog)s %(version)s")
def cli(
    topic_arg: str,
    topic_opt: Optional[str],
    select_opt: Optional[str],
    style_opt: Optional[str],
    format_opt: str,
    output_dir: str,
    headless: bool,
    interactive: bool,
    doctor: bool,
    overwrite: bool,
) -> None:
    """Video Agent: Automated professional video production from scratch."""
    if doctor:
        sys.exit(diagnose_cli())

    # Resolve topic from option or argument
    effective_topic = topic_opt if topic_opt is not None else topic_arg
    clean_topic = effective_topic.strip() if effective_topic else ""
    if not clean_topic:
        if headless:
            raise click.ClickException("Topic cannot be empty or whitespace in headless mode.")
        clean_topic = click.prompt("Enter video topic", type=str)
        clean_topic = clean_topic.strip()
        if not clean_topic:
            raise click.ClickException("Topic cannot be empty or whitespace.")

    # Validate --select
    if select_opt is not None:
        if not select_opt.isdigit() or int(select_opt) not in (1, 2, 3):
            raise click.ClickException(
                f"Invalid option selection '{select_opt}'. Must be one of: 1, 2, 3"
            )

    # Validate --style
    if style_opt is not None:
        matched_style = None
        for s in AVAILABLE_STYLES:
            if s.lower() == style_opt.strip().lower():
                matched_style = s
                break
        if not matched_style:
            raise click.ClickException(
                f"Invalid style '{style_opt}'. Must be one of: {', '.join(AVAILABLE_STYLES)}"
            )
        style_opt = matched_style

    # Validate --format
    fmt_lower = format_opt.strip().lower()
    if fmt_lower not in [f.lower() for f in VALID_FORMATS]:
        raise click.ClickException(
            f"Invalid format '{format_opt}'. Must be one of: 9:16, 16:9, both, vertical, horizontal"
        )

    if fmt_lower in ("9:16", "vertical"):
        formats_to_render = ["9:16"]
    elif fmt_lower in ("16:9", "horizontal"):
        formats_to_render = ["16:9"]
    else:
        formats_to_render = ["9:16", "16:9"]

    # Target directory setup
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Topic Research
    display_banner()
    console.print(f"[bold cyan]>>> Step 1:[/bold cyan] Researching topic: [bold green]{clean_topic}[/bold green]")
    research = research_topic(clean_topic)
    display_research_summary(research)

    # 2. Script Generation
    console.print("[bold cyan]>>> Step 2:[/bold cyan] Generating multi-option script breakdowns...")
    options = generate_script_options(research)
    display_options_table(options)

    # 3. Option Selection
    selected_option: VideoOptionSpec
    if select_opt is not None:
        idx = int(select_opt) - 1
        selected_option = options[idx]
        console.print(f"[green]Selection via --select:[/green] Option {select_opt} ({selected_option.style_name})")
    elif style_opt is not None:
        matched = [o for o in options if o.style_name == style_opt]
        selected_option = matched[0] if matched else options[0]
        console.print(f"[green]Selection via --style:[/green] Option {selected_option.option_id} ({selected_option.style_name})")
    elif headless:
        selected_option = options[0]
        console.print(f"[green]Selection via --headless:[/green] Defaulting to Option 1 ({selected_option.style_name})")
    else:
        # Interactive selection
        choice = click.prompt("Select option (1-3)", default="1", type=str)
        choice_clean = choice.strip()
        idx = int(choice_clean) - 1 if (choice_clean.isdigit() and 1 <= int(choice_clean) <= len(options)) else 0
        selected_option = options[idx]
        console.print(f"[green]Interactive Selection:[/green] Option {selected_option.option_id} ({selected_option.style_name})")

    console.print(f"Selected style: {selected_option.style_name}")
    console.print(f"\n[bold]Selected Option {selected_option.option_id}:[/bold] [bold magenta]{selected_option.style_name}[/bold magenta]")
    console.print(f"[bold]Title:[/bold] {selected_option.title}")

    # 4. Voiceover Synthesis & Subtitle Generation in isolated stage dir
    import tempfile
    topic_slug = sanitize_slug(clean_topic)
    with tempfile.TemporaryDirectory(prefix="va_stage_") as stagedir:
        stage_path = Path(stagedir)
        console.print("\n[bold cyan]>>> Step 3:[/bold cyan] Synthesizing neural voiceover...")
        asyncio.run(synthesize_all_scenes(selected_option, stage_path))

        # 5. Subtitle Generation
        console.print("[bold cyan]>>> Step 4:[/bold cyan] Generating synchronized millisecond subtitles...")
        asyncio.run(generate_all_subtitles(selected_option, stage_path))

        # 6. Video Composition & Dual-Format Rendering
        console.print(f"[bold cyan]>>> Step 5:[/bold cyan] Rendering video formats ({', '.join(formats_to_render)})...")
        rendered_files = render_video_option(selected_option, out_path, formats=formats_to_render, slug=topic_slug)

    # 7. Dual Delivery (Output dir + Project root)
    project_root = Path.cwd()
    for fmt_key, vpath in rendered_files.items():
        console.print(f"[bold green]✔ Rendered {fmt_key}:[/bold green] {vpath}")
        if project_root.resolve() != out_path.resolve():
            root_dest = project_root / vpath.name
            shutil.copy2(vpath, root_dest)
            console.print(f"[dim]  (Copied to project root: {root_dest.name})[/dim]")

    # 8. Artifact Serialization
    # research.json
    res_dict = research.model_dump()
    (out_path / "research.json").write_text(json.dumps(res_dict, indent=2, default=str), encoding="utf-8")

    # script.json
    script_dict = {
        "topic": clean_topic,
        "selected_option": selected_option.option_id,
        "style_name": selected_option.style_name,
        "estimated_duration": selected_option.estimated_duration,
        "scenes": [s.model_dump() for s in selected_option.scenes],
    }
    (out_path / "script.json").write_text(json.dumps(script_dict, indent=2, default=str), encoding="utf-8")

    # metadata.json
    video_filenames = [vpath.name for vpath in rendered_files.values()]
    if len(formats_to_render) > 1:
        aspect_ratio_str = "dual"
    elif "16:9" in formats_to_render:
        aspect_ratio_str = "16:9"
    elif "9:16" in formats_to_render:
        aspect_ratio_str = "9:16"
    else:
        aspect_ratio_str = "dual"

    formats_list = ["9:16", "16:9"] if aspect_ratio_str == "dual" else formats_to_render

    meta_dict = {
        "topic": clean_topic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_style": selected_option.style_name,
        "style": selected_option.style_name,
        "duration": selected_option.estimated_duration,
        "video_files": video_filenames,
        "formats": formats_list,
        "aspect_ratio": aspect_ratio_str,
        "status": "completed",
        "output_dir": str(out_path),
    }
    (out_path / "metadata.json").write_text(json.dumps(meta_dict, indent=2, default=str), encoding="utf-8")

    console.print("\n[bold green]✔ Video production completed successfully![/bold green]")
    console.print(f"Artifacts delivered to: [bold]{out_path}[/bold]")


# Expose main alias
main = cli

if __name__ == "__main__":
    cli()
