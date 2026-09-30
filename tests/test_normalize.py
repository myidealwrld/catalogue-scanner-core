import unittest

from catalogue_scanner_core import normalize_record


class NormalizeRecordTests(unittest.TestCase):
    def test_normalizes_common_aliases_and_relative_images(self):
        result = normalize_record({
            "name": "  Sample &amp; Shirt ",
            "permalink": "https://shop.example.test/products/shirt",
            "brand_name": "Example",
            "product_code": "SKU-1",
            "image": {"src": "/shirt.jpg"},
            "composition": "100% cotton",
            "availability": "InStock",
            "variants": [
                {"id": 4, "title": "Small", "price": "12.00"},
                {"id": 4, "title": "Small", "price": "12.00"},
            ],
        })
        self.assertEqual(result["title"], "Sample & Shirt")
        self.assertEqual(result["images"], ["https://shop.example.test/shirt.jpg"])
        self.assertEqual(result["materials"], ["100% cotton"])
        self.assertEqual(result["variants"][0]["id"], 4)
        self.assertEqual(len(result["variants"]), 1)
        self.assertEqual(result["evidence_urls"], ["https://shop.example.test/products/shirt"])

    def test_rejects_non_http_product_urls(self):
        with self.assertRaises(ValueError):
            normalize_record({"title": "No URL", "url": "javascript:alert(1)"})


if __name__ == "__main__":
    unittest.main()