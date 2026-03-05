import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FUNCTION_SRC = REPO_ROOT / "src" / "function_app"
if str(FUNCTION_SRC) not in sys.path:
    sys.path.insert(0, str(FUNCTION_SRC))

from extractor.runner import ExtractionRunner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generic API extraction job locally")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "configs" / "jobs" / "sample_api.json"),
        help="Path to a job config JSON file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "local_output"),
        help="Local output directory for parquet files and state",
    )
    args = parser.parse_args()

    runner = ExtractionRunner.for_local(local_output_dir=args.output_dir)
    result = runner.run_from_file(args.config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
