import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from vanam.CleanupOldImages import CleanupOldImages


class TestCleanupOldImages(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = self.temp_dir.name
        self.images_dir = os.path.join(self.base_dir, "images")
        self.metadata_dir = os.path.join(self.base_dir, "image-metadata")
        self.identifications_dir = os.path.join(self.base_dir, "identifications")
        self.aggregated_dir = os.path.join(self.base_dir, "aggregated")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.identifications_dir, exist_ok=True)
        os.makedirs(self.aggregated_dir, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_stem_files(self, stem: str, days_old: int) -> tuple[str, str]:
        shard = stem[:4]
        image_dir = os.path.join(self.images_dir, shard)
        metadata_dir = os.path.join(self.metadata_dir, shard)
        os.makedirs(image_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)

        image_path = os.path.join(image_dir, f"{stem}.png")
        metadata_path = os.path.join(metadata_dir, f"{stem}.json")
        with open(image_path, "wb") as f:
            f.write(b"png")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({"hash": stem}, f)

        ts = (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=days_old)
        ).timestamp()
        os.utime(image_path, (ts, ts))
        os.utime(metadata_path, (ts, ts))
        return image_path, metadata_path

    def _write_identification(self, stem: str) -> str:
        shard = stem[:4]
        ident_dir = os.path.join(self.identifications_dir, shard)
        os.makedirs(ident_dir, exist_ok=True)
        path = os.path.join(ident_dir, f"{stem}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"hash": stem}, f)
        return path

    def _write_aggregated(self, stems: list[str]) -> str:
        path = os.path.join(self.aggregated_dir, "all.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"imageHash": stem} for stem in stems], f)
        return path

    def test_run_deletes_only_old_untracked_stems(self):
        old_stem = "abcd1234abcd1234"
        identified_stem = "beef1234beef1234"
        aggregated_stem = "cafe1234cafe1234"
        fresh_stem = "dead1234dead1234"

        old_image, old_metadata = self._write_stem_files(old_stem, days_old=31)
        identified_image, identified_metadata = self._write_stem_files(
            identified_stem, days_old=31
        )
        aggregated_image, aggregated_metadata = self._write_stem_files(
            aggregated_stem, days_old=31
        )
        fresh_image, fresh_metadata = self._write_stem_files(
            fresh_stem, days_old=10
        )

        self._write_identification(identified_stem)
        self._write_aggregated([aggregated_stem])

        with patch("vanam.CleanupOldImages.DATA_IMAGES_DIR", self.images_dir), patch(
            "vanam.CleanupOldImages.DATA_IMAGE_METADATA_DIR", self.metadata_dir
        ), patch(
            "vanam.CleanupOldImages.DATA_IDENTIFICATIONS_DIR",
            self.identifications_dir,
        ), patch(
            "vanam.CleanupOldImages.DATA_AGGREGATED_ALL_PATH",
            os.path.join(self.aggregated_dir, "all.json"),
        ):
            result = CleanupOldImages().run()

        self.assertEqual(
            result,
            {
                "images_deleted": 1,
                "metadata_deleted": 1,
                "stems_deleted": 1,
            },
        )
        self.assertFalse(os.path.exists(old_image))
        self.assertFalse(os.path.exists(old_metadata))
        self.assertTrue(os.path.exists(identified_image))
        self.assertTrue(os.path.exists(identified_metadata))
        self.assertTrue(os.path.exists(aggregated_image))
        self.assertTrue(os.path.exists(aggregated_metadata))
        self.assertTrue(os.path.exists(fresh_image))
        self.assertTrue(os.path.exists(fresh_metadata))

    def test_run_keeps_stem_when_any_existing_file_is_fresh(self):
        stem = "face1234face1234"
        image_path, metadata_path = self._write_stem_files(stem, days_old=31)
        fresh_ts = (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=5)
        ).timestamp()
        os.utime(metadata_path, (fresh_ts, fresh_ts))

        with patch("vanam.CleanupOldImages.DATA_IMAGES_DIR", self.images_dir), patch(
            "vanam.CleanupOldImages.DATA_IMAGE_METADATA_DIR", self.metadata_dir
        ), patch(
            "vanam.CleanupOldImages.DATA_IDENTIFICATIONS_DIR",
            self.identifications_dir,
        ), patch(
            "vanam.CleanupOldImages.DATA_AGGREGATED_ALL_PATH",
            os.path.join(self.aggregated_dir, "all.json"),
        ):
            result = CleanupOldImages().run()

        self.assertEqual(
            result,
            {
                "images_deleted": 0,
                "metadata_deleted": 0,
                "stems_deleted": 0,
            },
        )
        self.assertTrue(os.path.exists(image_path))
        self.assertTrue(os.path.exists(metadata_path))


if __name__ == "__main__":
    unittest.main()