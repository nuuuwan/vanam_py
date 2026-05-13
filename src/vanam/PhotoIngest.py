import os
import re

import requests
from utils import Log

log = Log(__name__)


class PhotoIngest:
    """Queries Vercel Blob storage for new photos and saves them to
    data/photos, filtering out files outside the accepted size range."""

    PHOTO_SIZE_MIN_KB = 10
    PHOTO_SIZE_MAX_KB = 100

    VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"
    VERCEL_BLOB_PREFIX = "plant-images"
    DATA_PHOTOS_DIR = os.path.join("data", "photos")

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Vercel Blob token not provided. "
                "Set the BLOB_READ_WRITE_TOKEN environment variable."
            )
        os.makedirs(self.DATA_PHOTOS_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _list_blobs(self) -> list[dict]:
        """Return all blobs listed in the Vercel Blob store."""
        blobs = []
        cursor = None

        while True:
            params = {"limit": 1000, "prefix": self.VERCEL_BLOB_PREFIX}
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

        log.info(f"Found {len(blobs)} blob(s) in Vercel store.")
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

    def _is_valid_filename(self, filename: str) -> bool:
        """Return True if filename matches <16 hex chars>.png."""
        return bool(re.fullmatch(r"[0-9a-f]{16}\.png", filename))

    def _download_blob(self, blob: dict) -> str | None:
        """Download a single blob and save it to data/photos.

        Returns the local file path on success, or None if the file
        already exists.
        """
        filename = os.path.basename(blob["pathname"])

        if not self._is_valid_filename(filename):
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> list[str]:
        """Query Vercel for photos, apply size filters, and save to
        data/photos.

        Returns a list of file paths that were newly downloaded.
        """
        blobs = self._list_blobs()
        saved_paths = []

        for blob in blobs:
            if not self._is_valid_size(blob):
                continue

            dest = self._download_blob(blob)
            if dest:
                saved_paths.append(dest)

        log.info(f"Ingestion complete. {len(saved_paths)} new photo(s) saved.")
        return saved_paths
