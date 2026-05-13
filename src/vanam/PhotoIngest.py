import json
import os
import re

import requests
from utils import Log

log = Log(__name__)


class PhotoIngest:
    """Queries Vercel Blob storage for new photos and image metadata,
    saving them to data/images and data/image-metadata respectively."""

    PHOTO_SIZE_MIN_KB = 10
    PHOTO_SIZE_MAX_KB = 100

    VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"
    PHOTO_BLOB_PREFIX = "plant-images"
    METADATA_BLOB_PREFIX = "plant-image-metadata"
    DATA_PHOTOS_DIR = os.path.join("data", "images")
    DATA_IMAGE_METADATA_DIR = os.path.join("data", "image-metadata")

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Vercel Blob token not provided. "
                "Set the BLOB_READ_WRITE_TOKEN environment variable."
            )
        os.makedirs(self.DATA_PHOTOS_DIR, exist_ok=True)
        os.makedirs(self.DATA_IMAGE_METADATA_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _list_blobs(self, prefix: str) -> list[dict]:
        """Return all blobs under the given Vercel Blob prefix."""
        blobs = []
        cursor = None

        while True:
            params = {"limit": 1000, "prefix": prefix}
            if cursor:
                params["cursor"] = cursor

            response = requests.get(
                self.VERCEL_BLOB_API_URL,
                headers={"Authorization": f"Bearer {self.token}"},
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            blobs.extend(data.get("blobs", []))

            if data.get("hasMore"):
                cursor = data.get("cursor")
            else:
                break

        log.info(f"Found {len(blobs)} blob(s) under '{prefix}'.")
        return blobs

    def _is_valid_size(self, blob: dict) -> bool:
        """Return True if the blob's size falls within the accepted range."""
        size_kb = blob.get("size", 0) / 1024
        if size_kb < self.PHOTO_SIZE_MIN_KB:
            log.debug(
                f"Skipping {blob['pathname']} — too small "
                f"({size_kb:.1f} KB < {self.PHOTO_SIZE_MIN_KB} KB)."
            )
            return False
        if size_kb > self.PHOTO_SIZE_MAX_KB:
            log.debug(
                f"Skipping {blob['pathname']} — too large "
                f"({size_kb:.1f} KB > {self.PHOTO_SIZE_MAX_KB} KB)."
            )
            return False
        return True

    def _download_photo(self, blob: dict) -> str | None:
        """Download a photo blob to data/images/<stem[:4]>/<filename>."""
        filename = os.path.basename(blob["pathname"])

        if not re.fullmatch(r"[0-9a-f]{16}\.png", filename):
            log.debug(f"Skipping '{filename}' — not a valid photo name.")
            return None

        subdir = os.path.join(self.DATA_PHOTOS_DIR, filename[:4])
        os.makedirs(subdir, exist_ok=True)
        dest_path = os.path.join(subdir, filename)

        if os.path.exists(dest_path):
            log.debug(f"Already saved: {filename} — skipping.")
            return None

        response = requests.get(blob["url"], timeout=60)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            f.write(response.content)

        size_kb = len(response.content) / 1024
        log.info(f"Saved {filename} ({size_kb:.1f} KB) → {dest_path}")
        return dest_path

    def _download_metadata(self, blob: dict) -> str | None:
        """Download a metadata blob to
        data/image-metadata/<stem[:4]>/<filename>."""
        filename = os.path.basename(blob["pathname"])

        if not re.fullmatch(r"[0-9a-f]{16}\.json", filename):
            log.debug(f"Skipping '{filename}' — not a valid metadata name.")
            return None

        stem = os.path.splitext(filename)[0]
        subdir = os.path.join(self.DATA_IMAGE_METADATA_DIR, stem[:4])
        os.makedirs(subdir, exist_ok=True)
        dest_path = os.path.join(subdir, filename)

        if os.path.exists(dest_path):
            log.debug(f"Already saved: {filename} — skipping.")
            return None

        response = requests.get(blob["url"], timeout=30)
        response.raise_for_status()

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=2, ensure_ascii=False)

        log.info(f"Saved {filename} → {dest_path}")
        return dest_path

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> dict[str, list[str]]:
        """Fetch photos and image metadata from Vercel.

        Returns a dict with keys 'photos' and 'metadata', each containing
        a list of newly saved file paths.
        """
        photo_blobs = self._list_blobs(self.PHOTO_BLOB_PREFIX)
        metadata_blobs = self._list_blobs(self.METADATA_BLOB_PREFIX)

        saved_photos = []
        for blob in photo_blobs:
            if not self._is_valid_size(blob):
                continue
            dest = self._download_photo(blob)
            if dest:
                saved_photos.append(dest)

        saved_metadata = []
        for blob in metadata_blobs:
            dest = self._download_metadata(blob)
            if dest:
                saved_metadata.append(dest)

        log.info(
            f"Ingestion complete. "
            f"{len(saved_photos)} photo(s), "
            f"{len(saved_metadata)} metadata file(s) saved."
        )
        return {"photos": saved_photos, "metadata": saved_metadata}
