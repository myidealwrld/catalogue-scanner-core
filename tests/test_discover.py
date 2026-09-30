import json
import unittest

from catalogue_scanner_core.discover import (
    DiscoveryError,
    canonical_store_url,
    discover_catalogue,
    extract_jsonld_products,
)


class FakeClient:
    def __init__(self, json_map=None, text_map=None):
        self.json_map = json_map or {}
        self.text_map = text_map or {}

    def get_json(self, url):
        if url not in self.json_map:
            raise DiscoveryError("missing fixture")
        return self.json_map[url]

    def get_text(self, url):
        if url not in self.text_map:
            raise DiscoveryError("missing fixture")
        return self.text_map[url], url


class DiscoverTests(unittest.TestCase):
    def test_canonical_store_url(self):
        self.assertEqual(canonical_store_url("shop.example.test/path"), "https://shop.example.test/")

    def test_shopify_discovery(self):
        client = FakeClient(json_map={
            "https://shop.example.test/products.json?limit=250&page=1": {
                "products": [{"id": 1, "handle": "shirt", "title": "Shirt"}]
            }
        })
        result = discover_catalogue("https://shop.example.test", client=client)
        self.assertEqual(result["adapter"], "shopify")
        self.assertEqual(result["products"][0]["url"], "https://shop.example.test/products/shirt")

    def test_woocommerce_fallback(self):
        client = FakeClient(json_map={
            "https://woo.example.test/wp-json/wc/store/v1/products?per_page=100&page=1": [
                {"id": 3, "name": "Soap", "permalink": "https://woo.example.test/product/soap"}
            ]
        })
        result = discover_catalogue("woo.example.test", client=client)
        self.assertEqual(result["adapter"], "woocommerce")
        self.assertEqual(result["products"][0]["url"], "https://woo.example.test/product/soap")

    def test_sitemap_and_jsonld_fallback(self):
        sitemap = "<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://generic.example.test/products/bag</loc></url></urlset>"
        page = "<html><script type='application/ld+json'>" + json.dumps({
            "@context": "https://schema.org", "@type": "Product", "name": "Bag"
        }) + "</script></html>"
        client = FakeClient(text_map={
            "https://generic.example.test/sitemap.xml": sitemap,
            "https://generic.example.test/products/bag": page,
        })
        result = discover_catalogue("generic.example.test", client=client)
        self.assertEqual(result["adapter"], "json-ld-sitemap")
        self.assertEqual(result["products"][0]["name"], "Bag")
        self.assertEqual(result["products"][0]["url"], "https://generic.example.test/products/bag")

    def test_extracts_product_from_graph(self):
        page = '<script type="application/ld+json">{"@graph":[{"@type":"WebSite"},{"@type":"Product","name":"Tea"}]}</script>'
        products = extract_jsonld_products(page, "https://example.test/products/tea")
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Tea")


if __name__ == "__main__":
    unittest.main()
