"""Venue graph representation and loading for Sanket.

Loads venue definitions from YAML specs and builds NetworkX directed
or undirected graphs representing physical venue layouts.
"""

from pathlib import Path

import yaml

from sanket.schema import Venue


def load_venue(path: str | Path) -> Venue:
    """Load a venue YAML specification and validate it into a Venue model.

    Args:
        path: Path to the venue YAML file.

    Returns:
        Validated Venue object.

    Raises:
        FileNotFoundError: If the venue file does not exist.
        TypeError: If venue YAML content is not a dictionary.
        ValueError: If YAML syntax is invalid or venue data fails validation.
    """
    venue_path = Path(path)
    if not venue_path.exists():
        raise FileNotFoundError(f"Venue file not found: {venue_path}")

    try:
        with open(venue_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML in {venue_path}: {e}") from e

    if not isinstance(data, dict):
        raise TypeError(f"Venue YAML in {venue_path} must be a dictionary.")

    return Venue.model_validate(data)
