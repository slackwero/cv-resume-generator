"""Project paths used by the interface."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

DEFAULT_LANGUAGE = "en"
DEFAULT_TEMPLATE = "modern"
