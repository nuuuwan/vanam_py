import json
import os
import unittest
from unittest.mock import patch

from vanam.Identify import Identify

TEST_DIR = os.path.dirname(__file__)
TEST_IMAGE = os.path.join(TEST_DIR, "data", "image.png")
RAW_FIXTURE_PATH = os.path.join(TEST_DIR, "data", "plantnet.raw.json")


def _load_raw_fixture() -> dict:
    with open(RAW_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestPlantNet(unittest.TestCase):
    def setUp(self):
        api_key = os.environ.get("PLANTNET_API_KEY")
        if not api_key:
            self.fail("PLANTNET_API_KEY environment variable is not set")
        self.identify = Identify(api_key=api_key)

    def test_call_plantnet_raw(self):
        """_call_plantnet_raw must return a response matching the stored fixture."""
        expected = _load_raw_fixture()
        actual = self.identify._call_plantnet_raw(TEST_IMAGE)

        self.assertEqual(actual["results"], expected["results"])

    def test_call_plantnet(self):
        raw_fixture = _load_raw_fixture()
        expected = [
            {
                "confidence": 0.93118,
                "species": "Artocarpus heterophyllus Lam.",
                "genus": "Artocarpus",
                "family": "Moraceae",
                "commonNames": ["Jackfruit", "Nangka", "Jack"],
                "gbifId": "2984565",
                "iucnId": "",
                "iucnCategory": "",
                "powoId": "850389-1",
            },
            {
                "confidence": 0.04122,
                "species": "Artocarpus integer (Thunb.) Merr.",
                "genus": "Artocarpus",
                "family": "Moraceae",
                "commonNames": ["Chempedak", "Champedak", "Tjampedak"],
                "gbifId": "2984566",
                "iucnId": "61220334",
                "iucnCategory": "LC",
                "powoId": "582622-1",
            },
            {
                "confidence": 0.00127,
                "species": "Treculia africana Decne. ex Trécul",
                "genus": "Treculia",
                "family": "Moraceae",
                "commonNames": [
                    "African breadfruit",
                    "African-boxwood",
                    "African breadnut",
                ],
                "gbifId": "7895921",
                "iucnId": "87717226",
                "iucnCategory": "LC",
                "powoId": "856719-1",
            },
        ]

        with patch.object(
            self.identify, "_call_plantnet_raw", return_value=raw_fixture
        ):
            actual = self.identify._call_plantnet(TEST_IMAGE)

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
