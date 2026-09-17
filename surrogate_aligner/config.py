# =====================================================================================
# Surrogate Language Aligner
#
# Load project settings from config.toml (Python 3.11+).
# =====================================================================================

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


# Function:     build_config
# Inputs:       None
# Outputs:      config | file paths and tier names used by the pipeline (dict)
# Description:  Builds the pipeline configuration from the loaded TOML settings.

def build_config():
    # Store pipeline settings in one config dictionary
    config = {
        "audio_path": AUDIO_PATH,
        "elan_input_path": ELAN_INPUT_PATH,
        "input_tier": INPUT_TIER,
        "output_dir": OUTPUT_DIR,
        "output_tiers": OUTPUT_TIERS,
        "elan_output_path": ELAN_OUTPUT_PATH
    }

    # Return the pipeline configuration
    return config
