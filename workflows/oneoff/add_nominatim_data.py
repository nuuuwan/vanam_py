"""One-off: backfill nominatim_data for legacy identifications that lack it."""

import json
import os
import time

import requests

from src.vanam.Identify import Identify
from utils import Log

log = Log(__name__)

DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")


def _all_identification_paths():
    for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
        for fname in files:
            if fname.endswith(".json"):
                yield os.path.join(root, fname)


def run():
    all_paths = sorted(_all_identification_paths())
    total = len(all_paths)
    missing = sum(
        1
        for p in all_paths
        if "nominatim_data" not in json.load(open(p, encoding="utf-8"))
    )
    log.info(f"{total} total record(s); {missing} without nominatim data.")

    updated = 0
    skipped = 0

    for path in all_paths:
        with open(path, encoding="utf-8") as f:
            identification = json.load(f)

        if "nominatim_data" in identification:
            skipped += 1
            continue

        location = identification.get("image_metadata", {}).get(
            "imageLocation", {}
        )
        lat = location.get("latitude")
        lng = location.get("longitude")

        if lat is None or lng is None:
            log.warning(f"No coordinates in {path} — skipping.")
            skipped += 1
            continue

        log.info(f"Adding nominatim data to {path} …")
        nominatim_data = None
        for i_retry in range(5):
            try:
                nominatim_data = Identify._call_nominatim_raw(lat, lng)
                break
            except requests.HTTPError as exc:
                wait = 2**i_retry
                log.warning(
                    f"Nominatim error for {path} (attempt {i_retry + 1}/5): {exc} "
                    f"— retrying in {wait}s …"
                )
                time.sleep(wait)
        if nominatim_data is None:
            log.warning(f"All retries exhausted for {path} — skipping.")
            continue

        identification["nominatim_data"] = nominatim_data

        with open(path, "w", encoding="utf-8") as f:
            json.dump(identification, f, indent=2, ensure_ascii=False)

        updated += 1

    log.info(f"Done. {updated} updated, {skipped} skipped.")


if __name__ == "__main__":
    run()
