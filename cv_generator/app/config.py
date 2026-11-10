"""Project paths used by the interface."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

DEFAULT_LANGUAGE = "en"
DEFAULT_TEMPLATE = "modern"

MEGABYTE = 1024 * 1024
# The profile PDF weighs a few hundred KB and the full data archive a few MB: an upload
# larger than this is not LinkedIn's export.
MAX_UPLOAD_BYTES = 100 * MEGABYTE
