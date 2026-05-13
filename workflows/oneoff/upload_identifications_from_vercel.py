"""
One-off script: download existing plant identifications stored as JSON
files in the Vercel Blob `plant-metadata` prefix and save them to
data/identifications/<first 4 hex chars>/<name>.json.

    data/identifications/f3ec/f3ecf71f799b6ea0.json
"""

import json
import os
import re

import requests
from utils import Log

log = Log(__name__)

VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"
VERCEL_BLOB_PREFIX = "plant-metadata"
DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
IDENTIFICATION_FILENAME_RE = re.compile(r"[0-9a-f]{16}\.json")


def _get_token() -> str:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    if not token:
        raise ValueError(
            "Vercel Blob token not provided. "
            "Set the BLOB_READ_WRITE_TOKEN environment variable."
        )
    return token


def _list_blobs(token: str) -> list[dict]:
    blobs = []
    cursor = None

    while True:
        params = {"limit": 1000, "prefix": VERCEL_BLOB_PREFIX}
        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            VERCEL_BLOB_API_URL,
            headers={"Authorization": f"Bearer {token}"},
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


def _save_identification(filename_stem: str, identification: dict) -> str:
    subdir = os.path.join(DATA_IDENTIFICATIONS_DIR, filename_stem[:4])
    os.makedirs(subdir, exist_ok=True)
    dest_path = os.path.join(subdir, f"{filename_stem}.json")

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(identification, f, indent=2, ensure_ascii=False)

    log.info(f"Saved identification → {dest_path}")
    return dest_path


def run() -> list[str]:
    token = _get_token()
    os.makedirs(DATA_IDENTIFICATIONS_DIR, exist_ok=True)

    blobs = _list_blobs(token)
    saved_paths = []

    for blob in blobs:
        filename = os.path.basename(blob.get("pathname", ""))
        if not IDENTIFICATION_FILENAME_RE.fullmatch(filename):
            continue

        filename_stem = os.path.splitext(filename)[0]
        dest_path = os.path.join(
            DATA_IDENTIFICATIONS_DIR,
            filename_stem[:4],
            f"{filename_stem}.json",
        )
        if os.path.exists(dest_path):
            log.debug(f"Already saved: {dest_path} — skipping.")
            continue

        response = requests.get(blob["url"], timeout=30)
        response.raise_for_status()
        identification = response.json()

        saved_paths.append(_save_identification(filename_stem, identification))

    log.info(f"Done. {len(saved_paths)} identification(s) saved.")
    return saved_paths


if __name__ == "__main__":
    run()
