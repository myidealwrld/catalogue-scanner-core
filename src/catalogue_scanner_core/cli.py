"""Command-line interface for local product normalization."""

import argparse
import json
import sys

from .normalize import load_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize local catalogue JSON records")
    parser.add_argument("command", choices=["normalize"])
    parser.add_argument("input")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    try:
        result = json.dumps(load_records(args.input), ensure_ascii=False, indent=2) + "\n"
        if args.output == "-":
            sys.stdout.write(result)
        else:
            with open(args.output, "w", encoding="utf-8") as output_file:
                output_file.write(result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()