"""
video_agent.doctor - Environment diagnostics and health checking for Video Agent.
Provides programmatic validation functions and a rich CLI diagnostic runner.
"""

from __future__ import annotations

import argparse
import concurrent.futures
from dataclasses import dataclass, asdict
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional


@dataclass
class ToolStatus:
    """Represents the operational status and metadata of an environment tool or dependency."""
    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None
    details: Optional[str] = None
    category: str = "general"  # runtime, media_engine, voice_tts, recording, ui, general
    critical: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert ToolStatus to a JSON-serializable dictionary."""
        return asdict(self)


class EnvironmentReport(dict):
    """
    Dictionary mapping tool name -> ToolStatus with transparent alias resolution
    and case-insensitive lookup. Allows looking up tools by canonical name in any case,
    package name, or common alias without raising KeyError
    (e.g. 'FFmpeg' -> 'ffmpeg', 'cv2' -> 'opencv', 'edge_tts' -> 'edge-tts').
    """
    _ALIASES = {
        "cv2": "opencv",
        "opencv-python": "opencv",
        "edge_tts": "edge-tts",
        "edgetts": "edge-tts",
        "chromium": "playwright_chromium",
        "playwright-chromium": "playwright_chromium",
        "consola": "consola.ttf",
        "segoeui": "segoeui.ttf",
        "arial": "arial.ttf",
        "pil": "pillow",
    }

    def _resolve_canonical(self, key: object) -> str:
        k_lower = str(key).strip().lower()
        return self._ALIASES.get(k_lower, k_lower)

    def __getitem__(self, key: str) -> ToolStatus:
        canonical = self._resolve_canonical(key)
        return super().__getitem__(canonical)

    def __setitem__(self, key: str, value: ToolStatus) -> None:
        canonical = self._resolve_canonical(key)
        super().__setitem__(canonical, value)

    def get(self, key: str, default=None):
        canonical = self._resolve_canonical(key)
        return super().get(canonical, default)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, (str, bytes)):
            canonical = self._resolve_canonical(key)
            return super().__contains__(canonical)
        return super().__contains__(key)

    def pop(self, key: str, *args):
        canonical = self._resolve_canonical(key)
        return super().pop(canonical, *args)

    def setdefault(self, key: str, default=None):
        canonical = self._resolve_canonical(key)
        return super().setdefault(canonical, default)


def _extract_version(text: str, pattern: str) -> Optional[str]:
    """Helper to extract version string from CLI output using regex."""
    if not text:
        return None
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1) if match.groups() else match.group(0)
    return None


def _find_executable(name: str) -> Optional[str]:
    """
    Locates an executable on PATH, handling Windows PATH entries with surrounding quotes
    and stripping invalid whitespace.
    """
    path_env = os.environ.get("PATH", "")
    if not path_env:
        return None

    cleaned_entries = []
    for entry in path_env.split(os.pathsep):
        entry_clean = entry.strip().strip('"').strip("'")
        if entry_clean and os.path.exists(entry_clean):
            cleaned_entries.append(entry_clean)
    cleaned_path = os.pathsep.join(cleaned_entries) if cleaned_entries else None

    # First attempt with sanitized path
    found = shutil.which(name, path=cleaned_path)
    if found:
        return found
    return shutil.which(name)


def _run_cli_command(cmd: List[str], timeout: float = 3.0, shell: bool = False) -> subprocess.CompletedProcess:
    """Safely runs a CLI command with a strict timeout and output capture."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=shell,
        check=False,
    )


def _get_python_pkg_version(pkg_name: str, mod: Any = None) -> Optional[str]:
    """Safely obtains the version of a Python package without crashing on missing __version__."""
    if mod is not None:
        v = getattr(mod, "__version__", None)
        if v and isinstance(v, str):
            return v
    try:
        return importlib.metadata.version(pkg_name)
    except Exception:
        return None


def _get_python_pkg_path(pkg_name: str) -> Optional[str]:
    """Finds the filesystem path of an imported Python package."""
    try:
        spec = importlib.util.find_spec(pkg_name)
        if spec and spec.origin:
            return str(Path(spec.origin).resolve())
        mod = sys.modules.get(pkg_name)
        if mod and hasattr(mod, "__file__") and mod.__file__:
            return str(Path(mod.__file__).resolve())
    except Exception:
        pass
    return None


def _find_chromium_executable() -> Optional[str]:
    """
    Directly detects Playwright Chromium executable without recursive directory scans.
    Checks Playwright browsers.json target revision first, then shallow inspection of ms-playwright.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None
    ms_playwright = Path(local_app_data) / "ms-playwright"
    if not ms_playwright.is_dir():
        return None

    # Step 1: Query Playwright's browsers.json for exact expected revision
    try:
        import playwright
        pw_dir = Path(playwright.__file__).parent
        b_json = pw_dir / "driver" / "package" / "browsers.json"
        if b_json.is_file():
            data = json.loads(b_json.read_text(encoding="utf-8"))
            for b in data.get("browsers", []):
                if b.get("name") == "chromium":
                    rev = b.get("revision")
                    for sub in ["chrome-win64", "chrome-win", "chrome-headless-shell-win64"]:
                        candidate = ms_playwright / f"chromium-{rev}" / sub / "chrome.exe"
                        if candidate.is_file():
                            return str(candidate)
                        shell_candidate = ms_playwright / f"chromium_headless_shell-{rev}" / sub / "chrome-headless-shell.exe"
                        if shell_candidate.is_file():
                            return str(shell_candidate)
    except Exception:
        pass

    # Step 2: Shallow scan of ms-playwright top-level entries (depth <= 2, no recursive os.walk)
    try:
        for entry in ms_playwright.iterdir():
            if entry.is_dir() and "chromium" in entry.name.lower():
                for sub in entry.iterdir():
                    if sub.is_dir():
                        for exe in ["chrome.exe", "chrome-headless-shell.exe"]:
                            candidate = sub / exe
                            if candidate.is_file():
                                return str(candidate)
                    elif entry.is_dir():
                        for exe in ["chrome.exe", "chrome-headless-shell.exe"]:
                            candidate = entry / exe
                            if candidate.is_file():
                                return str(candidate)
    except Exception:
        pass

    return None


def _probe_npm_fast(npm_path: Optional[str]) -> ToolStatus:
    """Probes npm version via package.json manifest, falling back to CLI."""
    if not npm_path:
        return ToolStatus(
            name="npm",
            installed=False,
            version=None,
            path=None,
            details="Not found on PATH",
            category="runtime",
            critical=False,
        )

    p = Path(npm_path)
    candidates = [
        p.parent / "node_modules" / "npm" / "package.json",
        p.resolve().parent / "node_modules" / "npm" / "package.json",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "node_modules" / "npm" / "package.json",
    ]
    for pkg_json in candidates:
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                ver = data.get("version")
                if ver and isinstance(ver, str):
                    return ToolStatus(
                        name="npm",
                        installed=True,
                        version=ver.strip(),
                        path=npm_path,
                        details="Node package manager",
                        category="runtime",
                        critical=False,
                    )
            except Exception:
                pass

    try:
        res = _run_cli_command([npm_path, "--version"], timeout=2.5, shell=(sys.platform == "win32"))
        npm_ver = _extract_version(res.stdout, r"(\d+\.\d+\.\d+)") if res.returncode == 0 else None
        return ToolStatus(
            name="npm",
            installed=(res.returncode == 0 and npm_ver is not None),
            version=npm_ver,
            path=npm_path,
            details="Node package manager",
            category="runtime",
            critical=False,
        )
    except subprocess.TimeoutExpired:
        return ToolStatus(name="npm", installed=False, version=None, path=npm_path, details="Timeout during check", category="runtime", critical=False)
    except Exception as e:
        return ToolStatus(name="npm", installed=False, version=None, path=npm_path, details=str(e), category="runtime", critical=False)


def _probe_remotion_fast(remotion_path: Optional[str]) -> ToolStatus:
    """Probes Remotion CLI version dynamically via package.json manifest, falling back to CLI."""
    if not remotion_path:
        return ToolStatus(
            name="remotion",
            installed=False,
            version=None,
            path=None,
            details="Not found on PATH",
            category="media_engine",
            critical=False,
        )

    candidate_pkg_paths = [
        Path(remotion_path).resolve().parent / "node_modules" / "@remotion" / "cli" / "package.json",
        Path(remotion_path).parent / "node_modules" / "@remotion" / "cli" / "package.json",
        Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@remotion" / "cli" / "package.json",
        Path(remotion_path).resolve().parent.parent / "package.json",
    ]
    remotion_ver: Optional[str] = None
    for pkg_json in candidate_pkg_paths:
        try:
            if pkg_json.is_file():
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                v = data.get("version")
                if v and isinstance(v, str):
                    remotion_ver = v.strip()
                    break
        except Exception:
            pass

    if not remotion_ver:
        try:
            res = _run_cli_command(
                [remotion_path, "--version"],
                timeout=5.0,
                shell=(sys.platform == "win32"),
            )
            output = (res.stdout or "") + " " + (res.stderr or "")
            remotion_ver = _extract_version(output, r"@remotion/cli\s+([0-9.]+)") or _extract_version(output, r"(\d+\.\d+\.\d+)")
        except Exception:
            remotion_ver = None

    return ToolStatus(
        name="remotion",
        installed=(remotion_ver is not None or remotion_path is not None),
        version=remotion_ver,
        path=remotion_path,
        details="Remotion React-based video generation CLI",
        category="media_engine",
        critical=False,
    )


def check_environment() -> EnvironmentReport:
    """
    Runs comprehensive health checks across all required tools, runtimes, video engines,
    TTS synthesizers, recording tools, and fonts. Never raises an unhandled exception.
    Executes external CLI subprocesses concurrently via ThreadPoolExecutor.
    """
    report = EnvironmentReport()

    # 1. Runtimes: python, pip
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    report["python"] = ToolStatus(
        name="python",
        installed=True,
        version=py_ver,
        path=sys.executable,
        details=f"Python {platform.python_implementation()} {platform.architecture()[0]}",
        category="runtime",
        critical=True,
    )

    pip_path = _find_executable("pip") or os.path.join(os.path.dirname(sys.executable), "Scripts", "pip.exe")
    pip_ver = _get_python_pkg_version("pip")
    report["pip"] = ToolStatus(
        name="pip",
        installed=(pip_ver is not None),
        version=pip_ver,
        path=pip_path if (pip_path and os.path.exists(pip_path)) else None,
        details="Python package installer",
        category="runtime",
        critical=True,
    )

    # 2. Python-based media engines, TTS, recorders, and UI packages (zero subprocesses, fast importlib)
    # Manim
    manim_path = _find_executable("manim") or _get_python_pkg_path("manim")
    manim_ver = _get_python_pkg_version("manim")
    report["manim"] = ToolStatus(
        name="manim",
        installed=(manim_ver is not None and manim_path is not None),
        version=manim_ver,
        path=manim_path,
        details="Manim Community programmatic animation engine",
        category="media_engine",
        critical=True,
    )

    # OpenCV (cv2)
    cv2_ver = _get_python_pkg_version("opencv-python")
    cv2_path = _get_python_pkg_path("cv2")
    if not cv2_ver or not cv2_path:
        try:
            import cv2
            cv2_ver = cv2_ver or getattr(cv2, "__version__", None)
            cv2_path = cv2_path or getattr(cv2, "__file__", None)
        except Exception:
            pass
    report["opencv"] = ToolStatus(
        name="opencv",
        installed=(cv2_ver is not None and cv2_path is not None),
        version=cv2_ver,
        path=cv2_path,
        details="OpenCV computer vision and image processing",
        category="media_engine",
        critical=True,
    )

    # MoviePy
    moviepy_ver = _get_python_pkg_version("moviepy")
    moviepy_path = _get_python_pkg_path("moviepy")
    report["moviepy"] = ToolStatus(
        name="moviepy",
        installed=(moviepy_ver is not None and moviepy_path is not None),
        version=moviepy_ver,
        path=moviepy_path,
        details="MoviePy video editing and cuts suite",
        category="media_engine",
        critical=True,
    )

    # Pillow
    pillow_ver = _get_python_pkg_version("pillow")
    pillow_path = _get_python_pkg_path("PIL")
    report["pillow"] = ToolStatus(
        name="pillow",
        installed=(pillow_ver is not None and pillow_path is not None),
        version=pillow_ver,
        path=pillow_path,
        details="Pillow Python Imaging Library for raster rendering",
        category="media_engine",
        critical=True,
    )

    # Pydub
    pydub_ver = _get_python_pkg_version("pydub")
    pydub_path = _get_python_pkg_path("pydub")
    report["pydub"] = ToolStatus(
        name="pydub",
        installed=(pydub_ver is not None and pydub_path is not None),
        version=pydub_ver,
        path=pydub_path,
        details="Pydub high-level audio manipulation suite",
        category="media_engine",
        critical=True,
    )

    # Edge-TTS
    edge_path = _find_executable("edge-tts") or _get_python_pkg_path("edge_tts")
    edge_ver = _get_python_pkg_version("edge-tts")
    report["edge-tts"] = ToolStatus(
        name="edge-tts",
        installed=(edge_ver is not None and edge_path is not None),
        version=edge_ver,
        path=edge_path,
        details="Microsoft Edge Neural TTS voiceover synthesizer",
        category="voice_tts",
        critical=True,
    )

    # Pyttsx3
    pyttsx3_ver = _get_python_pkg_version("pyttsx3")
    pyttsx3_path = _get_python_pkg_path("pyttsx3")
    report["pyttsx3"] = ToolStatus(
        name="pyttsx3",
        installed=(pyttsx3_ver is not None),
        version=pyttsx3_ver,
        path=pyttsx3_path,
        details="Offline SAPI5 text-to-speech fallback",
        category="voice_tts",
        critical=False,
    )

    # gTTS
    gtts_ver = _get_python_pkg_version("gTTS")
    gtts_path = _get_python_pkg_path("gtts")
    report["gtts"] = ToolStatus(
        name="gtts",
        installed=(gtts_ver is not None),
        version=gtts_ver,
        path=gtts_path,
        details="Google Translate text-to-speech fallback",
        category="voice_tts",
        critical=False,
    )

    # Playwright python package
    playwright_path = _find_executable("playwright") or _get_python_pkg_path("playwright")
    playwright_ver = _get_python_pkg_version("playwright")
    report["playwright"] = ToolStatus(
        name="playwright",
        installed=(playwright_ver is not None and playwright_path is not None),
        version=playwright_ver,
        path=playwright_path,
        details="Playwright headless automation framework",
        category="recording",
        critical=True,
    )

    # Questionary
    q_ver = _get_python_pkg_version("questionary")
    q_path = _get_python_pkg_path("questionary")
    report["questionary"] = ToolStatus(
        name="questionary",
        installed=(q_ver is not None and q_path is not None),
        version=q_ver,
        path=q_path,
        details="Questionary interactive CLI selection prompt",
        category="ui",
        critical=True,
    )

    # Rich
    rich_ver = _get_python_pkg_version("rich")
    rich_path = _get_python_pkg_path("rich")
    report["rich"] = ToolStatus(
        name="rich",
        installed=(rich_ver is not None and rich_path is not None),
        version=rich_ver,
        path=rich_path,
        details="Rich terminal formatting and console logging suite",
        category="ui",
        critical=True,
    )

    # Pygments
    pyg_ver = _get_python_pkg_version("Pygments")
    pyg_path = _get_python_pkg_path("pygments")
    report["pygments"] = ToolStatus(
        name="pygments",
        installed=(pyg_ver is not None),
        version=pyg_ver,
        path=pyg_path,
        details="Pygments code syntax highlighting engine",
        category="ui",
        critical=False,
    )

    # 3. Chromium Headless (fast shallow scan)
    chrome_path = _find_chromium_executable()
    chromium_installed = chrome_path is not None and os.path.exists(chrome_path)
    report["playwright_chromium"] = ToolStatus(
        name="playwright_chromium",
        installed=chromium_installed,
        version="Chromium Headless" if chromium_installed else None,
        path=chrome_path if chromium_installed else None,
        details="Headless Chromium browser for terminal code demo recording" if chromium_installed else "Chromium browser binary not found in ms-playwright",
        category="recording",
        critical=True,
    )

    # 4. Windows Fonts
    font_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
    for font_name in ["consola.ttf", "segoeui.ttf", "arial.ttf"]:
        font_path = os.path.join(font_dir, font_name)
        exists = os.path.exists(font_path)
        report[font_name] = ToolStatus(
            name=font_name,
            installed=exists,
            version="System Font" if exists else None,
            path=font_path if exists else None,
            details=f"TrueType Font ({font_name})" if exists else "Font not found",
            category="general",
            critical=False,
        )

    # 5. Fast metadata probes for npm & remotion
    report["npm"] = _probe_npm_fast(_find_executable("npm"))
    report["remotion"] = _probe_remotion_fast(_find_executable("remotion"))

    # 6. External CLI binaries executed concurrently via ThreadPoolExecutor
    cli_jobs: Dict[str, tuple] = {}
    cli_specs = [
        ("node", ["--version"], r"v?(\d+\.\d+\.\d+)", False, "Node.js JavaScript runtime", "runtime", False),
        ("winget", ["--version"], r"v?(\d+\.\d+\.\d+)", False, "Windows Package Manager CLI", "runtime", False),
        ("git", ["--version"], r"git version (\S+)", False, "Git distributed version control", "runtime", False),
        ("ffmpeg", ["-version"], r"ffmpeg version (\S+)", False, "FFmpeg multimedia compositor with libx264, aac, libass", "media_engine", True),
        ("ffprobe", ["-version"], r"ffprobe version (\S+)", False, "FFprobe multimedia stream analyzer", "media_engine", True),
        ("vhs", ["--version"], r"vhs version (v?\S+)", False, "Charm VHS terminal recording tool", "recording", False),
        ("ttyd", ["--version"], r"ttyd version (\S+)", False, "ttyd web terminal sharing tool", "recording", False),
    ]

    for name, cmd_args, pattern, shell, details, cat, crit in cli_specs:
        exe_path = _find_executable(name)
        if exe_path:
            cli_jobs[name] = ([exe_path] + cmd_args, pattern, shell, details, cat, crit)
        else:
            report[name] = ToolStatus(
                name=name,
                installed=False,
                version=None,
                path=None,
                details="Not found on PATH",
                category=cat,
                critical=crit,
            )

    def _execute_cli_job(item: tuple) -> tuple:
        tool_name, (cmd, pattern, is_shell, desc, category, is_critical) = item
        tool_path = cmd[0]
        try:
            res = _run_cli_command(cmd, timeout=5.0, shell=is_shell)
            combined = (res.stdout or "") + " " + (res.stderr or "")
            v = _extract_version(combined, pattern) if (res.returncode == 0 or len(res.stdout) > 0) else None
            return tool_name, ToolStatus(
                name=tool_name,
                installed=(res.returncode == 0 and v is not None),
                version=v,
                path=tool_path,
                details=desc,
                category=category,
                critical=is_critical,
            )
        except subprocess.TimeoutExpired:
            return tool_name, ToolStatus(
                name=tool_name,
                installed=False,
                version=None,
                path=tool_path,
                details="Timeout during check",
                category=category,
                critical=is_critical,
            )
        except Exception as e:
            return tool_name, ToolStatus(
                name=tool_name,
                installed=False,
                version=None,
                path=tool_path,
                details=str(e),
                category=category,
                critical=is_critical,
            )

    if cli_jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(cli_jobs), 8)) as executor:
            futures = [executor.submit(_execute_cli_job, item) for item in cli_jobs.items()]
            for fut in concurrent.futures.as_completed(futures):
                t_name, status = fut.result()
                report[t_name] = status

    return report


# Expose alias for tests that mock check_environment and need the original function
_original_check_environment = check_environment


def ensure_dependencies(raise_error: bool = False, report: Optional[EnvironmentReport] = None) -> bool:
    """
    Validates that all critical dependencies are ready.
    Returns True if healthy. Returns False or raises RuntimeError if critical dependencies are missing.
    """
    if report is None:
        report = check_environment()
    critical_missing = [
        tool.name for tool in report.values()
        if tool.critical and not tool.installed
    ]
    if critical_missing:
        msg = f"Missing critical dependencies: {', '.join(critical_missing)}"
        if raise_error:
            raise RuntimeError(msg)
        return False
    return True


def diagnose_cli(args: Optional[List[str]] = None) -> int:
    """
    CLI diagnostic runner formatting Rich tables, outputting JSON, or running quiet checks.
    Returns exit code 0 if all critical pass, 1 if any critical fail, 2 on invalid arguments.
    """
    if args is None:
        args = []

    parser = argparse.ArgumentParser(description="Video Agent Environment Diagnostics")
    parser.add_argument("--json", action="store_true", help="Output diagnostics report as JSON")
    parser.add_argument("--check-only", action="store_true", help="Quiet mode, return exit code only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    report = check_environment()
    is_ready = ensure_dependencies(raise_error=False, report=report)

    # Quiet check-only mode
    if parsed_args.check_only:
        return 0 if is_ready else 1

    # JSON output mode
    if parsed_args.json:
        data = {k: v.to_dict() for k, v in report.items()}
        print(json.dumps(data, indent=2))
        return 0 if is_ready else 1

    # Rich formatted interactive table
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        # Accommodate narrow terminal width if configured
        term_width = None
        if "COLUMNS" in os.environ:
            try:
                term_width = max(int(os.environ["COLUMNS"]), 40)
            except ValueError:
                pass

        console = Console(width=term_width)
        table = Table(title="Video Agent Environment Diagnostics", show_lines=False)
        table.add_column("Category", style="dim", no_wrap=True)
        table.add_column("Tool", style="bold", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Version", style="cyan")
        table.add_column("Path", style="dim", overflow="ellipsis")
        table.add_column("Details", overflow="fold")

        passed_count = 0
        warn_count = 0
        fail_count = 0

        for name, tool in report.items():
            if tool.installed:
                passed_count += 1
                status_str = "[bold green]PASS [✓][/bold green]"
            elif not tool.critical:
                warn_count += 1
                status_str = "[bold yellow]WARN [!][/bold yellow]"
            else:
                fail_count += 1
                status_str = "[bold red]FAIL [✗][/bold red]"

            ver_display = tool.version or "-"
            path_display = tool.path or "-"
            if not parsed_args.verbose and path_display != "-" and len(path_display) > 35:
                path_display = "..." + path_display[-32:]

            table.add_row(
                tool.category,
                name,
                status_str,
                ver_display,
                path_display,
                tool.details or "",
            )

        console.print(table)

        summary_msg = (
            f"[bold]Total Checks:[/bold] {len(report)} | "
            f"[bold green]Passed:[/bold green] {passed_count} | "
            f"[bold yellow]Warnings (Optional):[/bold yellow] {warn_count} | "
            f"[bold red]Failed (Critical):[/bold red] {fail_count}\n"
        )
        if is_ready:
            summary_msg += "[bold green]✔ Environment is HEALTHY and READY for video production.[/bold green]"
            console.print(Panel(summary_msg, border_style="green", title="System Health Summary"))
            return 0
        else:
            summary_msg += "[bold red]✘ Environment has MISSING CRITICAL DEPENDENCIES.[/bold red]\nPlease install missing critical tools before running pipeline."
            console.print(Panel(summary_msg, border_style="red", title="System Health Summary"))
            return 1

    except Exception:
        # Fallback plain text output if Rich formatting fails
        print("Video Agent Environment Diagnostics")
        for name, tool in report.items():
            status = "PASS" if tool.installed else ("WARN" if not tool.critical else "FAIL")
            print(f"[{status}] {name}: {tool.version} ({tool.path})")
        return 0 if is_ready else 1


if __name__ == "__main__":
    sys.exit(diagnose_cli(sys.argv[1:]))
