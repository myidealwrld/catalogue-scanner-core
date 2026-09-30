# Catalogue Scanner Core

A small, dependency-free Python package for normalizing already-discovered commerce records into a stable product-data shape. It does not crawl storefronts or score products.

## Why

The production workspace has a reusable product-evidence gate and text cleanup, but its discovery pipeline is not separated from private scoring, datasets, and deployment infrastructure. This staging copy isolates only record normalization while that boundary is resolved.

## Features

- Normalize common Shopify-, WooCommerce-, and JSON-LD-shaped input records when those records have already been collected.
- Preserve source/evidence URLs and normalize variants, prices, images, availability, materials, ingredients, and sourcing evidence.
- Emit a versioned JSON product record using the schema in `schema/product.schema.json`.
- No network access or runtime dependencies.

## Installation

Python 3.10 or newer is required. From this directory:

```sh
python3 -m pip install .
```

## Quick start

```sh
python3 -m catalogue_scanner_core normalize examples/input.json --output /tmp/products.json
```

The command writes a JSON array. A sanitized expected result is in `examples/output.json`.

## Configuration

There are no credentials or environment variables. This package only transforms local JSON input.

## Architecture

`schema/product.schema.json` defines the public record. `src/catalogue_scanner_core/normalize.py` adapts known field aliases to that schema. Network discovery is deliberately absent until a safe, production-proven adapter can be separated from the private scanner layer.

## Development and testing

```sh
python3 -m pip install -e '.[test]'
python3 -m unittest discover -s tests -v
```

## Security

Input is treated as untrusted data. The normalizer does not fetch URLs, execute HTML, or follow links. Do not put credentials or customer exports in examples or fixtures.

## Licence

Apache-2.0. See `LICENSE`.