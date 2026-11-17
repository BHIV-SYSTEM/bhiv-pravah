from __future__ import annotations

from importlib import import_module

__all__ = ["MultiAppControlPlane", "AppOverrideManager"]


def __getattr__(name: str):
	if name == "MultiAppControlPlane":
		return import_module("control_plane.multi_app_control_plane").MultiAppControlPlane
	if name == "AppOverrideManager":
		return import_module("control_plane.app_override_manager").AppOverrideManager
	raise AttributeError(f"module 'control_plane' has no attribute {name!r}")
