"""YAML configuration loading and validation for Sanket.

Handles loading default settings, per-task knobs, quota definitions,
and model configuration profiles.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class QuotasConfig(BaseModel):
    """Quota targets per question type."""

    DIRECT: int
    BINDING: int
    CLOSURE: int
    OVERRIDE: int
    EGOCENTRIC: int
    ABSENT: int
    model_config = ConfigDict(extra="allow")


class DefaultConfig(BaseModel):
    """Default benchmark configuration model."""

    master_seed: int
    total_tasks: int
    keep_tasks: int
    blind_threshold: float
    blind_samples: int
    pair_fraction: float
    prompt_version: str
    quotas: QuotasConfig
    model_config = ConfigDict(extra="allow")


class ModelProfile(BaseModel):
    """Configuration profile for a model adapter."""

    name: str
    adapter: str
    model_id: str
    rpm: int = 10
    enabled: bool = True
    base_url: str | None = None
    model_config = ConfigDict(extra="allow")


class ModelsConfig(BaseModel):
    """Model evaluation profiles configuration model."""

    models: list[ModelProfile]
    blind_model: str
    model_config = ConfigDict(extra="allow")


def _resolve_config_path(default_filename: str, path: str | Path | None = None) -> Path:
    """Resolve configuration file path."""
    if path is not None:
        return Path(path)
    cwd_path = Path("config") / default_filename
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "config" / default_filename


def load_default_config(path: str | Path | None = None) -> DefaultConfig:
    """Load and validate the default system configuration from YAML.

    Args:
        path: Optional path to default.yaml. Defaults to config/default.yaml.

    Returns:
        Validated DefaultConfig instance.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        TypeError: If YAML content is not a dictionary.
        ValueError: If YAML is malformed or required keys are missing.
    """
    cfg_path = _resolve_config_path("default.yaml", path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML in {cfg_path}: {e}") from e

    if not isinstance(data, dict):
        raise TypeError(f"Configuration in {cfg_path} must be a dictionary.")

    try:
        return DefaultConfig.model_validate(data)
    except ValidationError as e:
        missing = [
            ".".join(str(loc) for loc in err["loc"])
            for err in e.errors()
            if err["type"] == "missing"
        ]
        if missing:
            raise ValueError(
                f"Missing required configuration key(s) in {cfg_path}: {', '.join(missing)}"
            ) from e
        raise ValueError(f"Invalid configuration in {cfg_path}: {e}") from e


def load_models_config(path: str | Path | None = None) -> ModelsConfig:
    """Load and validate the model evaluation configuration from YAML.

    Args:
        path: Optional path to models.yaml. Defaults to config/models.yaml.

    Returns:
        Validated ModelsConfig instance.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        TypeError: If YAML content is not a dictionary.
        ValueError: If YAML is malformed or required keys are missing.
    """
    cfg_path = _resolve_config_path("models.yaml", path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML in {cfg_path}: {e}") from e

    if not isinstance(data, dict):
        raise TypeError(f"Configuration in {cfg_path} must be a dictionary.")

    try:
        return ModelsConfig.model_validate(data)
    except ValidationError as e:
        missing = [
            ".".join(str(loc) for loc in err["loc"])
            for err in e.errors()
            if err["type"] == "missing"
        ]
        if missing:
            raise ValueError(
                f"Missing required configuration key(s) in {cfg_path}: {', '.join(missing)}"
            ) from e
        raise ValueError(f"Invalid configuration in {cfg_path}: {e}") from e
