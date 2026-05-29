from __future__ import annotations

from pathlib import Path

CONTAINER_WORKFLOW_ROOT = "/workspace/workflow"


class PathTranslator:
    """Map host paths under a user workflow tree to container paths."""

    def __init__(self, host_workflow_root: str, *, container_root: str = CONTAINER_WORKFLOW_ROOT) -> None:
        self.host_root = Path(host_workflow_root).expanduser().resolve()
        self.container_root = container_root.rstrip("/")

    def host_to_container(self, path: str) -> str:
        resolved = Path(path).expanduser().resolve()
        rel = resolved.relative_to(self.host_root)
        return f"{self.container_root}/{rel.as_posix()}"

    def container_to_host(self, path: str) -> str:
        raw = path.strip()
        prefix = self.container_root + "/"
        if raw == self.container_root:
            return str(self.host_root)
        if not raw.startswith(prefix):
            raise ValueError(f"Path is outside container workflow root: {path}")
        rel = raw[len(prefix) :]
        return str((self.host_root / rel).resolve())

    def is_host_under_workspace(self, path: str) -> bool:
        try:
            Path(path).expanduser().resolve().relative_to(self.host_root)
            return True
        except ValueError:
            return False
