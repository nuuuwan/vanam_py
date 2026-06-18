import datetime
import json
import os
import re

from utils import Log

log = Log(__name__)

DATA_IMAGES_DIR = os.path.join("data", "images")
DATA_IMAGE_METADATA_DIR = os.path.join("data", "image-metadata")
DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
DATA_AGGREGATED_ALL_PATH = os.path.join("data", "aggregated", "all.json")


class CleanupOldImages:
    """Remove old local images and metadata that never became records."""

    OLD_IMAGE_DAYS = 30
    IMAGE_FILENAME_RE = re.compile(r"([0-9a-f]{16})\.png")
    METADATA_FILENAME_RE = re.compile(r"([0-9a-f]{16})\.json")

    def __init__(self, now: datetime.datetime | None = None):
        self.now = now or datetime.datetime.now(datetime.UTC)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _all_identified_stems() -> set[str]:
        stems = set()
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in files:
                if fname.endswith(".json"):
                    stems.add(os.path.splitext(fname)[0])
        return stems

    @staticmethod
    def _all_aggregated_stems() -> set[str]:
        if not os.path.exists(DATA_AGGREGATED_ALL_PATH):
            return set()
        try:
            with open(DATA_AGGREGATED_ALL_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(
                f"Could not read aggregated data at {DATA_AGGREGATED_ALL_PATH}: {exc}"
            )
            return set()

        if not isinstance(data, list):
            log.warning(
                f"Expected a list in {DATA_AGGREGATED_ALL_PATH}; got {type(data).__name__}."
            )
            return set()

        stems = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            image_hash = item.get("imageHash")
            if isinstance(image_hash, str) and image_hash:
                stems.add(image_hash)
        return stems

    def _is_old(self, path: str) -> bool:
        try:
            modified = datetime.datetime.fromtimestamp(
                os.path.getmtime(path), datetime.UTC
            )
        except OSError as exc:
            log.warning(f"Could not stat {path}: {exc}")
            return False
        return (self.now - modified).days > self.OLD_IMAGE_DAYS

    @staticmethod
    def _remove_file(path: str) -> bool:
        try:
            os.remove(path)
            log.info(f"Removed {path}")
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def _stem_file_paths(stem: str) -> list[str]:
        shard = stem[:4]
        return [
            os.path.join(DATA_IMAGES_DIR, shard, f"{stem}.png"),
            os.path.join(DATA_IMAGE_METADATA_DIR, shard, f"{stem}.json"),
        ]

    def _all_existing_files_old(self, stem: str) -> bool:
        existing_paths = [
            path for path in self._stem_file_paths(stem) if os.path.exists(path)
        ]
        if not existing_paths:
            return False
        return all(self._is_old(path) for path in existing_paths)

    def _iter_old_untracked_stems(self) -> list[str]:
        protected_stems = self._all_identified_stems() | self._all_aggregated_stems()
        candidate_stems = set()

        for root, _, files in os.walk(DATA_IMAGES_DIR):
            for fname in files:
                match = self.IMAGE_FILENAME_RE.fullmatch(fname)
                if not match:
                    continue
                stem = match.group(1)
                if stem in protected_stems:
                    continue
                if self._all_existing_files_old(stem):
                    candidate_stems.add(stem)

        for root, _, files in os.walk(DATA_IMAGE_METADATA_DIR):
            for fname in files:
                match = self.METADATA_FILENAME_RE.fullmatch(fname)
                if not match:
                    continue
                stem = match.group(1)
                if stem in protected_stems:
                    continue
                if self._all_existing_files_old(stem):
                    candidate_stems.add(stem)

        return sorted(candidate_stems)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> dict[str, int]:
        """Delete old images and metadata with no identification or aggregate."""
        stems = self._iter_old_untracked_stems()
        deleted_images = 0
        deleted_metadata = 0

        for stem in stems:
            image_path, metadata_path = self._stem_file_paths(stem)
            deleted_images += int(self._remove_file(image_path))
            deleted_metadata += int(self._remove_file(metadata_path))

        log.info(
            f"CleanupOldImages complete. Removed {deleted_images} image(s) and "
            f"{deleted_metadata} metadata file(s) across {len(stems)} stem(s)."
        )
        return {
            "images_deleted": deleted_images,
            "metadata_deleted": deleted_metadata,
            "stems_deleted": len(stems),
        }