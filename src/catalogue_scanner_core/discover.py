"""Generic, read-only ecommerce catalogue discovery helpers."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Iterable

USER_AGENT = "catalogue-scanner-core/0.2 (+https://github.com/myidealwrld/catalogue-scanner-core)"
DEFAULT_TIMEOUT = 20
PRODUCT_PATH_RE = re.compile(r"/(?:products?|shop|product-category)/", re.I)


class DiscoveryError(RuntimeError):
    """Raised when a discovery adapter cannot complete safely."""


@dataclass
class HttpClient:
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = USER_AGENT
    delay: float = 0.0

    def get_bytes(self, url: str) -> tuple[bytes, str, str]:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            raise DiscoveryError(f"HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise DiscoveryError(f"Request failed for {url}: {exc.reason}") from exc
        if self.delay:
            time.sleep(self.delay)
        return body, content_type, final_url

    def get_json(self, url: str) -> Any:
        body, _, _ = self.get_bytes(url)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiscoveryError(f"Expected JSON from {url}") from exc

    def get_text(self, url: str) -> tuple[str, str]:
        body, _, final_url = self.get_bytes(url)
        return body.decode("utf-8", errors="replace"), final_url


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self._chunks: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = {k.lower(): (v or "") for k, v in attrs}
        if values.get("type", "").split(";")[0].strip().lower() == "application/ld+json":
            self._capture = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self.blocks.append("".join(self._chunks).strip())
            self._capture = False
            self._chunks = []


def canonical_store_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("store URL must be HTTP(S)")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def _product_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _product_nodes(item)
        return
    if not isinstance(value, dict):
        return
    graph = value.get("@graph")
    if graph is not None:
        yield from _product_nodes(graph)
    node_type = value.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if any(str(t).lower() == "product" for t in types if t):
        yield value


def extract_jsonld_products(html_text: str, page_url: str) -> list[dict[str, Any]]:
    parser = _JsonLdParser()
    parser.feed(html_text)
    products: list[dict[str, Any]] = []
    for block in parser.blocks:
        if not block:
            continue
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in _product_nodes(payload):
            product = dict(node)
            product.setdefault("url", page_url)
            product.setdefault("source_platform", "json-ld")
            products.append(product)
    return products


def discover_shopify(base_url: str, client: HttpClient, max_pages: int = 20) -> list[dict[str, Any]]:
    base = canonical_store_url(base_url)
    products: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for page in range(1, max_pages + 1):
        url = urllib.parse.urljoin(base, f"products.json?limit=250&page={page}")
        try:
            payload = client.get_json(url)
        except DiscoveryError:
            if page == 1:
                return []
            break
        batch = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(batch, list) or not batch:
            break
        added = 0
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("id") or raw.get("handle") or raw.get("title") or "")
            if key and key in seen_ids:
                continue
            if key:
                seen_ids.add(key)
            item = dict(raw)
            handle = item.get("handle")
            if handle and not item.get("url"):
                item["url"] = urllib.parse.urljoin(base, f"products/{handle}")
            item.setdefault("source_platform", "shopify")
            products.append(item)
            added += 1
        if added == 0 or len(batch) < 250:
            break
    return products


def discover_woocommerce(base_url: str, client: HttpClient, max_pages: int = 20) -> list[dict[str, Any]]:
    base = canonical_store_url(base_url)
    products: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = urllib.parse.urljoin(base, f"wp-json/wc/store/v1/products?{query}")
        try:
            payload = client.get_json(url)
        except DiscoveryError:
            if page == 1:
                return []
            break
        if not isinstance(payload, list) or not payload:
            break
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item.setdefault("source_platform", "woocommerce")
            item.setdefault("url", item.get("permalink"))
            products.append(item)
        if len(payload) < 100:
            break
    return products


def _xml_locations(xml_text: str) -> tuple[str, list[str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise DiscoveryError("Invalid sitemap XML") from exc
    kind = root.tag.rsplit("}", 1)[-1].lower()
    locations = [
        (node.text or "").strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].lower() == "loc" and (node.text or "").strip()
    ]
    return kind, locations


def discover_sitemap_urls(base_url: str, client: HttpClient, max_sitemaps: int = 40, max_urls: int = 500) -> list[str]:
    base = canonical_store_url(base_url)
    queue = [urllib.parse.urljoin(base, "sitemap.xml")]
    visited: set[str] = set()
    product_urls: list[str] = []
    while queue and len(visited) < max_sitemaps and len(product_urls) < max_urls:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)
        try:
            xml_text, _ = client.get_text(sitemap_url)
            kind, locations = _xml_locations(xml_text)
        except DiscoveryError:
            continue
        if kind == "sitemapindex":
            for location in locations:
                if location not in visited and location not in queue:
                    queue.append(location)
        elif kind == "urlset":
            for location in locations:
                if PRODUCT_PATH_RE.search(urllib.parse.urlparse(location).path) and location not in product_urls:
                    product_urls.append(location)
                    if len(product_urls) >= max_urls:
                        break
    return product_urls


def discover_jsonld_from_urls(urls: Iterable[str], client: HttpClient, max_products: int = 200) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for url in urls:
        if len(products) >= max_products:
            break
        try:
            html_text, final_url = client.get_text(url)
        except DiscoveryError:
            continue
        for product in extract_jsonld_products(html_text, final_url):
            products.append(product)
            if len(products) >= max_products:
                break
    return products


def discover_catalogue(base_url: str, client: HttpClient | None = None, max_pages: int = 20, max_products: int = 500) -> dict[str, Any]:
    """Discover products using public storefront surfaces, in priority order."""
    client = client or HttpClient()
    base = canonical_store_url(base_url)

    shopify = discover_shopify(base, client, max_pages=max_pages)
    if shopify:
        return {"adapter": "shopify", "store_url": base, "products": shopify[:max_products]}

    woo = discover_woocommerce(base, client, max_pages=max_pages)
    if woo:
        return {"adapter": "woocommerce", "store_url": base, "products": woo[:max_products]}

    urls = discover_sitemap_urls(base, client, max_urls=max_products)
    jsonld = discover_jsonld_from_urls(urls, client, max_products=max_products)
    return {
        "adapter": "json-ld-sitemap" if jsonld else "none",
        "store_url": base,
        "discovered_urls": urls,
        "products": jsonld,
    }
