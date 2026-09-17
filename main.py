# =====================================================================================
# Surrogate Language Aligner
#
# Launch the surrogate language alignment pipeline.
# =====================================================================================

from surrogate_aligner.config import build_config
from surrogate_aligner.pipeline import run_pipeline


# Function:     main
# Inputs:       None
# Outputs:      None
# Description:  Main project pipeline.

def main():
    # Print project header
    print("=== SURROGATE LANGUAGE ALIGNER ===\n")

    # Store pipeline settings in one config dictionary
    config = build_config()

    # Run the full pipeline
    alignment, confidence = run_pipeline(config)

    # Print final summary
    print("\n=== Processing Complete ===")
    print(f"  - Aligned items: {len(alignment)}")
    print(f"  - Confidence: {confidence:.2f}")
    print(f"  - ELAN saved to: {config['elan_output_path']}")
    print()


if __name__ == "__main__":
    main()
