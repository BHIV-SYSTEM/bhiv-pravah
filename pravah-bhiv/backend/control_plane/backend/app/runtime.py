import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RuntimeContext:
    agent: object
    control_plane: object
    environment: str


_RUNTIME_CONTEXT = None
_RUNTIME_LOCK = threading.Lock()


def _resolve_project_root() -> Path:
    configured_root = os.getenv("PROJECT_ROOT", "").strip()
    if configured_root:
        candidate = Path(configured_root).resolve()
        if (candidate / "agent_runtime.py").exists() and (candidate / "core").exists():
            return candidate

    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent

    if (project_root / "agent_runtime.py").exists() and (project_root / "core").exists():
        return project_root

    sibling_repo = project_root / "multi-agent-control-plane-main"
    if (sibling_repo / "agent_runtime.py").exists() and (sibling_repo / "core").exists():
        return sibling_repo

    raise RuntimeError(
        "Could not locate project root. Set PROJECT_ROOT to the folder containing agent_runtime.py"
    )


def ensure_project_context() -> Path:
    project_root = _resolve_project_root()
    os.chdir(project_root)
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root


def _ensure_project_root_on_path() -> None:
    ensure_project_context()


def _start_agent_loop(agent: object) -> None:
    thread = threading.Thread(target=agent.run, daemon=True)
    thread.start()


def bootstrap_runtime() -> RuntimeContext:
    global _RUNTIME_CONTEXT

    if _RUNTIME_CONTEXT is not None:
        return _RUNTIME_CONTEXT

    with _RUNTIME_LOCK:
        if _RUNTIME_CONTEXT is not None:
            return _RUNTIME_CONTEXT

        ensure_project_context()

        from agent_runtime import AgentRuntime
        from control_plane.multi_app_control_plane import MultiAppControlPlane

        environment = os.getenv("ENVIRONMENT", "dev")
        agent = AgentRuntime(env=environment)
        control_plane = MultiAppControlPlane(env=environment)
        _start_agent_loop(agent)

        _RUNTIME_CONTEXT = RuntimeContext(
            agent=agent,
            control_plane=control_plane,
            environment=environment,
        )

    return _RUNTIME_CONTEXT


def get_runtime_context() -> RuntimeContext:
    context = _RUNTIME_CONTEXT
    if context is None:
        return bootstrap_runtime()
    return context
