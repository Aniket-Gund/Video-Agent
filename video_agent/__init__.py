"""
Video Agent - Automated video creation pipeline and interactive CLI.
"""

__version__ = "0.1.0"


def __getattr__(name: str):
    if name in (
        "ToolStatus",
        "EnvironmentReport",
        "check_environment",
        "ensure_dependencies",
        "diagnose_cli",
    ):
        import video_agent.doctor as doctor
        return getattr(doctor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "ToolStatus",
    "EnvironmentReport",
    "check_environment",
    "ensure_dependencies",
    "diagnose_cli",
]
