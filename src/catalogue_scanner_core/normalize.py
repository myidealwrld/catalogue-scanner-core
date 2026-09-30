"""Map discovered commerce records into the public product schema."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urljoin, urlparse


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (Mapping, list, tuple)):
        return None
    value = re.sub(r"\s+", " ", html.unescape(str(value))).strip()
    return value or None


def _first(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _url(value: Any, base_url: str | None = None) -> str | None:
    text = _text(value)
    if not text:
        return None
    if (text.startswith("//") or text.startswith("/")) and base_url:
        text = urljoin(base_url, text)
    parsed = urlparse(text)
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _variant(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        key: value[key]
        for key in ("id", "title", "sku", "price", "available", "options", "url")
        if key in value and value[key] is not None
    }


def _brand(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = _first(value, "name", "title")
    return _text(value)


def _price(value: Any, source: Mapping[str, Any]) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, Mapping):
        aliases = {
            "price": "price",
            "lowPrice": "lowPrice",
            "highPrice": "highPrice",
            "priceCurrency": "priceCurrency",
            "currency": "currency",
            "currency_code": "priceCurrency",
        }
        result = {out: value[key] for key, out in aliases.items() if key in value and value[key] is not None}
        return result or None
    return {"price": value, "currency": _text(source.get("currency"))}


def normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize common Shopify, WooCommerce, and JSON-LD product aliases."""
    nested = record.get("product")
    source = nested if isinstance(nested, Mapping) else record
    raw_url = _first(source, "url", "product_url", "permalink", "link")
    url = _url(raw_url, _text(_first(source, "base_url", "shop_url")))
    if not url:
        raise ValueError("product record needs an absolute HTTP(S) URL")

    variants = []
    variant_keys = set()
    for item in _list(source.get("variants")):
        variant = _variant(item)
        if variant is None:
            continue
        key = tuple(str(variant.get(field, "")) for field in ("id", "sku", "title", "price"))
        if key == ("", "", "", "") or key not in variant_keys:
            variants.append(variant)
            variant_keys.add(key)

    image_values = _list(_first(source, "images", "image"))
    images = []
    for item in image_values:
        candidate = item.get("src") or item.get("url") if isinstance(item, Mapping) else item
        normalized = _url(candidate, url)
        if normalized and normalized not in images:
            images.append(normalized)

    def texts(*keys: str) -> list[str]:
        values = []
        for key in keys:
            for item in _list(source.get(key)):
                text = _text(item)
                if text and text not in values:
                    values.append(text)
        return values

    evidence_urls = []
    for candidate in _list(_first(source, "evidence_urls", "source_urls", "source_url")):
        normalized = _url(candidate, url)
        if normalized and normalized not in evidence_urls:
            evidence_urls.append(normalized)
    if url not in evidence_urls:
        evidence_urls.insert(0, url)

    offers = source.get("offers")
    availability = _first(source, "availability", "stock_status")
    if not availability and isinstance(offers, Mapping):
        availability = offers.get("availability")
    if availability is None and "is_in_stock" in source:
        availability = "InStock" if source.get("is_in_stock") else "OutOfStock"

    return {
        "schema_version": "1.0",
        "source_platform": _text(_first(source, "source_platform", "platform")),
        "product_id": _text(_first(source, "product_id", "id")),
        "title": _text(_first(source, "title", "name")) or "",
        "brand": _brand(_first(source, "brand", "brand_name", "vendor")),
        "url": url,
        "sku": _text(_first(source, "sku", "product_code")),
        "variants": variants,
        "price": _price(_first(source, "price", "offers", "prices"), source),
        "images": images,
        "availability": _text(availability),
        "materials": texts("materials", "material", "composition"),
        "ingredients": texts("ingredients", "ingredient_list"),
        "sourcing_evidence": texts("sourcing_evidence", "disclosures", "evidence"),
        "evidence_urls": evidence_urls,
    }


def load_records(path: str) -> list[dict[str, Any]]:
    """Load an array or a single record from a local JSON file."""
    with open(path, encoding="utf-8") as source_file:
        data = json.load(source_file)
    if isinstance(data, Mapping):
        data = data.get("products", [data])
    if not isinstance(data, list) or not all(isinstance(item, Mapping) for item in data):
        raise ValueError("input JSON must be a record or an array of records")
    return [normalize_record(item) for item in data]
