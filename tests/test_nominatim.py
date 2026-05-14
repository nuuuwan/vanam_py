import json
import os
import unittest

from vanam.Identify import Identify

NOMINATIM_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "data", "nominatim.raw.json"
)


def _load_nominatim_fixture() -> dict:
    with open(NOMINATIM_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestNominatim(unittest.TestCase):
    def test_nominatim(self):
        """_call_nominatim_raw must return a response matching the stored fixture."""
        expected = _load_nominatim_fixture()
        lat = float(expected["lat"])
        lng = float(expected["lon"])
        actual = Identify._call_nominatim_raw(lat, lng)
        print(json.dumps(actual, indent=2, ensure_ascii=False))
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
