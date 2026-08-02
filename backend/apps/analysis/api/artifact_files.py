"""Safe local file resolution for visualization artifact API responses."""

from __future__ import annotations

from pathlib import Path

from rest_framework.exceptions import NotFound

VISUALIZATION_ROOT = Path("outputs") / "visualizations"


def default_repo_root() -> Path:
    """Return the repository root for artifact file resolution."""
    return Path(__file__).resolve().parents[4]


def resolve_visualization_artifact_path(relative_path: str) -> Path:
    """Resolve a registered visualization path without exposing local paths."""
    registered_path = Path(relative_path)
    generic_error = "Visualization artifact image is not available."

    if registered_path.is_absolute() or ".." in registered_path.parts:
        raise NotFound(generic_error)
    if not registered_path.is_relative_to(VISUALIZATION_ROOT):
        raise NotFound(generic_error)

    repo_root = default_repo_root().resolve()
    resolved_path = (repo_root / registered_path).resolve()
    if not resolved_path.is_relative_to(repo_root):
        raise NotFound(generic_error)
    if not resolved_path.is_relative_to((repo_root / VISUALIZATION_ROOT).resolve()):
        raise NotFound(generic_error)
    if not resolved_path.exists() or not resolved_path.is_file():
        raise NotFound(generic_error)

    return resolved_path
