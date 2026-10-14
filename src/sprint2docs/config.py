"""Validated local resource limits; configuration is not imported artifact content."""

from pathlib import Path

import yaml

from .models import ImportLimits


def load_limits(path: str | Path) -> ImportLimits:
    with Path(path).open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("configuration_size_limit")
    return ImportLimits.model_validate(yaml.safe_load(raw))
