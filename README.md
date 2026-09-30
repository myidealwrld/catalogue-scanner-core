# Catalogue Scanner Core

A dependency-free Python toolkit for discovering public ecommerce catalogue data and normalizing product records into one stable schema.

## Features

- Shopify public `products.json` discovery
- WooCommerce Store API discovery
- Sitemap traversal
- JSON-LD Product extraction
- Product normalization across common Shopify, WooCommerce, and schema.org field shapes
- Variants, price, images, availability, materials, ingredients, sourcing evidence, and source URLs
- CLI and importable Python API
- No Hold The Throne scoring, private datasets, credentials, or production infrastructure

## Installation

Python 3.10+:

```sh
git clone https://github.com/myidealwrld/catalogue-scanner-core.git
cd catalogue-scanner-core
python3 -m pip install .
```

## Scan a storefront

```sh
catalogue-scan discover https://example.com --output products.json
```

or:

```sh
python3 -m catalogue_scanner_core discover https://example.com --output products.json
```

The scanner tries public storefront surfaces in this order:

1. Shopify `/products.json`
2. WooCommerce Store API
3. `sitemap.xml` + JSON-LD Product records

Use `--max-products`, `--max-pages`, and `--delay` to bound requests. Use `--raw` to keep adapter-native product records instead of normalizing them.

## Normalize existing JSON

```sh
catalogue-normalize normalize examples/input.json --output products.json
```

The public schema is in `schema/product.schema.json`.

## Python API

```python
from catalogue_scanner_core import discover_catalogue, normalize_record

result = discover_catalogue("https://example.com")
normalized = [normalize_record(item) for item in result["products"]]
```

## Responsible use

This project only reads public storefront surfaces. Respect site terms, robots guidance where applicable, rate limits, and applicable law. Use `--delay` for considerate crawling. It does not bypass authentication, paywalls, access controls, or anti-bot systems.

## Development

```sh
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

The test suite covers Shopify, WooCommerce, sitemap/JSON-LD discovery, and normalization without making network requests.

## Security

The scanner does not require credentials. Treat downloaded catalogue data as untrusted input and do not add customer/private datasets to the repository.

## License

Apache-2.0. See `LICENSE`.
