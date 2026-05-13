import os
import re

import requests
from utils import Log

log = Log(__name__)


class Cleanup:
    """Deletes Vercel Blob entries that have already been ingested locally.

    A blob is considered processed when its corresponding local file exists:
      - plant-images  → data/images/<stem[:4]>/<stem>.png
      - plant-image-metadata → data/image-metadata/<stem[:4]>/<stem>.json
    """

    VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"
    PHOTO_BLOB_PREFIX = "plant-images"
    METADATA_BLOB_PREFIX = "plant-image-metadata"
    DATA_PHOTOS_DIR = os.path.join("data", "images")
    DATA_IMAGE_METADATA_DIR = os.path.join("data", "image-metadata")

    # Vercel Blob delete accepts up to 1 000 URLs per request.
    DELETE_BATCH_SIZE = 1000

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Vercel Blob token not provided. "
                "Set the BLOB_READ_WRITE_TOKEN environment variable."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _list_blobs(self, prefix: str) -> list[dict]:
        """Return all blobs under the given prefix."""
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

    def _is_photo_ingested(self, blob: dict) -> bool:
        filename = os.path.basename(blob["pathname"])
        if not re.fullmatch(r"[0-9a-f]{16}\.png", filename):
            return False
        stem = os.path.splitext(filename)[0]
        local_path = os.path.join(self.DATA_PHOTOS_DIR, stem[:4], filename)
        return os.path.exists(local_path)

    def _is_metadata_ingested(self, blob: dict) -> bool:
        filename = os.path.basename(blob["pathname"])
        if not re.fullmatch(r"[0-9a-f]{16}\.json", filename):
            return False
        stem = os.path.splitext(filename)[0]
        local_path = os.path.join(
            self.DATA_IMAGE_METADATA_DIR, stem[:4], filename
        )
        return os.path.exists(local_path)

    def _delete_blobs(self, urls: list[str]) -> None:
        """Delete blobs in batches of DELETE_BATCH_SIZE."""
        if not urls:
            return

        delete_url = f"{self.VERCEL_BLOB_API_URL}/delete"
        for i in range(0, len(urls), self.DELETE_BATCH_SIZE):
            batch = urls[i: i + self.DELETE_BATCH_SIZE]
            response = requests.post(
                delete_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"urls": batch},
                timeout=30,
            )
            response.raise_for_status()
            log.info(f"Deleted {len(batch)} blob(s) from Vercel.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> dict[str, int]:
        """Delete all ingested blobs from Vercel storage.

        Returns a dict with counts of deleted photos and metadata entries.
        """
        photo_blobs = self._list_blobs(self.PHOTO_BLOB_PREFIX)
        metadata_blobs = self._list_blobs(self.METADATA_BLOB_PREFIX)

        photo_urls = [
            b["url"] for b in photo_blobs if self._is_photo_ingested(b)
        ]
        metadata_urls = [
            b["url"] for b in metadata_blobs if self._is_metadata_ingested(b)
        ]

        log.info(
            f"{len(photo_urls)} photo(s) and "
            f"{len(metadata_urls)} metadata file(s) queued for deletion."
        )

        self._delete_blobs(photo_urls)
        self._delete_blobs(metadata_urls)

        log.info(
            f"Cleanup complete. "
            f"Deleted {len(photo_urls)} photo(s) and "
            f"{len(metadata_urls)} metadata file(s) from Vercel."
        )
        return {
            "photos_deleted": len(photo_urls),
            "metadata_deleted": len(metadata_urls),
        }
