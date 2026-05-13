import datetime
import json
import os

from utils import Log

log = Log(__name__)

DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
DATA_IMAGES_DIR = os.path.join("data", "images")
DATA_IMAGE_METADATA_DIR = os.path.join("data", "image-metadata")


class CleanupLowConf:
    """Removes locally stored data for low-confidence, old identifications.

    A record is deleted when BOTH conditions are met:
      - Top PlantNet prediction confidence < CONFIDENCE_THRESHOLD
      - Photo was taken more than MAX_AGE_DAYS days ago
    """

    CONFIDENCE_THRESHOLD = 0.20
    MAX_AGE_DAYS = 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_identifications(self):
        """Yield (path, data) for all identification JSONs."""
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in sorted(files):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, encoding="utf-8") as f:
                        yield path, json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    log.warning(f"Skipping {path}: {exc}")

    def _is_low_confidence(self, data: dict) -> bool:
        results = data.get("plantnet", {}).get("results", [])
        if not results:
            return True
        return results[0].get("score", 0) < self.CONFIDENCE_THRESHOLD

    def _is_old(self, data: dict) -> bool:
        ut = data.get("image_metadata", {}).get("utImageTaken")
        if not ut:
            return False
        try:
            taken = datetime.datetime.utcfromtimestamp(int(ut))
            age = datetime.datetime.utcnow() - taken
            return age.days > self.MAX_AGE_DAYS
        except (ValueError, OSError):
            return False

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            os.remove(path)
            log.info(f"Removed {path}")
        except FileNotFoundError:
            pass

    def _delete_record(self, ident_path: str, data: dict) -> None:
        stem = data.get("hash", "")
        if not stem:
            return

        shard = stem[:4]

        self._remove_file(ident_path)
        self._remove_file(os.path.join(DATA_IMAGES_DIR, shard, f"{stem}.png"))
        self._remove_file(
            os.path.join(DATA_IMAGE_METADATA_DIR, shard, f"{stem}.json")
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Delete records that are low-confidence and older than 28 days.

        Returns the number of records deleted.
        """
        deleted = 0
        for path, data in self._iter_identifications():
            if self._is_low_confidence(data) and self._is_old(data):
                predictions = data.get("plantNetPredictions", [{}])
                conf = predictions[0].get("confidence", 0)
                log.info(
                    f"Deleting low-confidence old record: "
                    f"{data.get('imageHash')} "
                    f"(conf={conf:.0%})"
                )
                self._delete_record(path, data)
                deleted += 1

        log.info(f"CleanupLowConf complete. {deleted} record(s) removed.")
        return deleted
