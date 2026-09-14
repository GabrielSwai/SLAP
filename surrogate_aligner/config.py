"""Load project settings from config.toml (Python 3.11+)."""

from pathlib import Path
import tomllib


PROJECT_DIR = Path(__file__).resolve().parent.parent

with (PROJECT_DIR / "config.toml").open("rb") as file:
    config = tomllib.load(file)

INPUT = config["INPUT"]
INPUT_TIER = config["INPUT_TIER"]

# Resolve relative directories against the project, not the launch directory.
DATA_DIR = PROJECT_DIR / config["DATA_DIR"]
AUDIO_PATH = DATA_DIR / f"{INPUT}.wav"
ELAN_INPUT_PATH = DATA_DIR / f"{INPUT}.eaf"

OUTPUT_DIR = PROJECT_DIR / config["OUTPUT_DIR"]
ELAN_OUTPUT_PATH = OUTPUT_DIR / config["OUTPUT_FILENAME"]
OUTPUT_TIERS = config["OUTPUT_TIERS"]
