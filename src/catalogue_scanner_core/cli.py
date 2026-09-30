"""Command-line interface for catalogue discovery and normalization."""

from __future__ import annotations

import argparse
import json
import sys

from .discover import DiscoveryError, HttpClient, discover_catalogue
from .normalize import load_records, normalize_record


def _write_json(value, output: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output == "-":
        sys.stdout.write(rendered)
    else:
        with open(output, "w", encoding="utf-8") as output_file:
            output_file.write(rendered)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Discover and normalize public ecommerce catalogue data")
    sub = parser.add_subparsers(dest="command", required=True)

    normalize = sub.add_parser("normalize", help="Normalize already-collected product JSON")
    normalize.add_argument("input")
    normalize.add_argument("--output", default="-")

    discover = sub.add_parser("discover", help="Discover public product records from a storefront")
    discover.add_argument("store_url")
    discover.add_argument("--output", default="-")
    discover.add_argument("--max-pages", type=int, default=20)
    discover.add_argument("--max-products", type=int, default=500)
    discover.add_argument("--delay", type=float, default=0.0, help="Delay between requests in seconds")
    discover.add_argument("--raw", action="store_true", help="Return adapter-native records without normalization")

    args = parser.parse_args(argv)
    try:
        if args.command == "normalize":
            _write_json(load_records(args.input), args.output)
            return 0

        client = HttpClient(delay=max(args.delay, 0.0))
        result = discover_catalogue(
            args.store_url,
            client=client,
            max_pages=max(1, args.max_pages),
            max_products=max(1, args.max_products),
        )
        if not args.raw:
            normalized = []
            errors = []
            for index, product in enumerate(result.get("products", [])):
                try:
                    normalized.append(normalize_record(product))
                except ValueError as exc:
                    errors.append({"index": index, "error": str(exc)})
            result["products"] = normalized
            if errors:
                result["normalization_errors"] = errors
        _write_json(result, args.output)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, DiscoveryError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
