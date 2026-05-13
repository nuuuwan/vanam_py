import json
import os
import unittest

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


if __name__ == "__main__":
    unittest.main()
