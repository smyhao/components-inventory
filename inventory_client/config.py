from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".components-inventory"
CONFIG_PATH = CONFIG_DIR / "config.json"


def empty_config() -> dict[str, Any]:
    return {"default_profile": "", "profiles": {}}


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return empty_config()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return empty_config()
    if not isinstance(data, dict):
        return empty_config()
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        data["profiles"] = {}
    data.setdefault("default_profile", "")
    return data


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def get_profile(config: dict[str, Any], profile: str | None) -> dict[str, Any]:
    name = profile or config.get("default_profile") or ""
    profiles = config.get("profiles") or {}
    item = profiles.get(name) if name else None
    return dict(item or {})


def set_profile_value(profile: str, key: str, value: str, path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = load_config(path)
    profiles = config.setdefault("profiles", {})
    item = profiles.setdefault(profile, {})
    item[key] = value
    if not config.get("default_profile"):
        config["default_profile"] = profile
    save_config(config, path)
    return config


def set_default_profile(profile: str, path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = load_config(path)
    config.setdefault("profiles", {}).setdefault(profile, {})
    config["default_profile"] = profile
    save_config(config, path)
    return config
