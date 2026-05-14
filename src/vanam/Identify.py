import json
import os
import re

import requests

from utils import Log

log = Log(__name__)

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
NOMINATIM_API_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "vanam_py/1.0"
DATA_IMAGES_DIR = os.path.join("data", "images")
DATA_IMAGE_METADATA_DIR = os.path.join("data", "image-metadata")
DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
PHOTO_FILENAME_RE = re.compile(r"[0-9a-f]{16}\.png")


class Identify:
    """Finds photos in data/images that have no corresponding
    identification in data/identifications, submits them to the
    PlantNet API, and saves the results as JSON."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("PLANTNET_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "PlantNet API key not provided. "
                "Set the PLANTNET_API_KEY environment variable."
            )

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _all_photo_stems(self) -> set[str]:
        """Return the hash stems of all photos in data/images."""
        stems = set()
        for root, _, files in os.walk(DATA_IMAGES_DIR):
            for fname in files:
                if PHOTO_FILENAME_RE.fullmatch(fname):
                    stems.add(os.path.splitext(fname)[0])
        return stems

    def _all_identified_stems(self) -> set[str]:
        """Return the hash stems that already have an identification."""
        stems = set()
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in files:
                if fname.endswith(".json"):
                    stems.add(os.path.splitext(fname)[0])
        return stems

    def _unidentified_stems(self) -> list[str]:
        return sorted(self._all_photo_stems() - self._all_identified_stems())

    # ------------------------------------------------------------------
    # Image metadata
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image_metadata(stem: str) -> dict:
        """Load metadata from data/image-metadata, or return empty dict."""
        path = os.path.join(DATA_IMAGE_METADATA_DIR, stem[:4], f"{stem}.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # PlantNet API
    # ------------------------------------------------------------------

    def _call_plantnet_raw(self, photo_path: str) -> dict:
        """Submit a photo to PlantNet and return the raw API response dict."""
        with open(photo_path, "rb") as f:
            response = requests.post(
                PLANTNET_API_URL,
                params={"api-key": self.api_key, "lang": "en"},
                files=[
                    (
                        "images",
                        (os.path.basename(photo_path), f, "image/png"),
                    )
                ],
                data={"organs": ["auto"]},
                timeout=60,
            )
        response.raise_for_status()
        raw = response.json()
        log.debug(json.dumps(raw, indent=2, ensure_ascii=False))
        return raw

    # ------------------------------------------------------------------
    # Nominatim API
    # ------------------------------------------------------------------

    @staticmethod
    def _call_nominatim_raw(lat: float, lng: float) -> dict:
        """Reverse-geocode a coordinate with Nominatim and return the raw response dict."""
        response = requests.get(
            NOMINATIM_API_URL,
            params={"lat": lat, "lon": lng, "format": "json"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        raw = response.json()
        log.debug(json.dumps(raw, indent=2, ensure_ascii=False))
        return raw

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self, stem: str, identification: dict) -> str:
        subdir = os.path.join(DATA_IDENTIFICATIONS_DIR, stem[:4])
        os.makedirs(subdir, exist_ok=True)
        dest_path = os.path.join(subdir, f"{stem}.json")
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(identification, f, indent=2, ensure_ascii=False)
        log.info(f"Saved → {dest_path}")
        return dest_path

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> list[str]:
        """Identify all unidentified photos and save results.

        Returns a list of newly written identification file paths.
        """
        pending = self._unidentified_stems()
        log.info(f"{len(pending)} photo(s) to identify.")
        saved_paths = []

        for stem in pending:
            photo_path = os.path.join(
                DATA_IMAGES_DIR, stem[:4], f"{stem}.png"
            )
            if not os.path.exists(photo_path):
                log.debug(f"Photo not found on disk: {photo_path}")
                continue

            log.info(f"Identifying {stem} …")
            try:
                image_metadata = self._load_image_metadata(stem)
                plantnet_data = self._call_plantnet_raw(photo_path)
                location = image_metadata.get("imageLocation", {})
                lat = location.get("latitude")
                lng = location.get("longitude")
                nominatim_data = (
                    self._call_nominatim_raw(lat, lng)
                    if lat is not None and lng is not None
                    else {}
                )
            except requests.HTTPError as exc:
                log.warning(f"PlantNet error for {stem}: {exc}")
                continue

            identification = {
                "hash": stem,
                "image_metadata": image_metadata,
                "plantnet_data": plantnet_data,
                "nominatim_data": nominatim_data,
            }

            saved_paths.append(self._save(stem, identification))

        log.info(f"Done. {len(saved_paths)} identification(s) saved.")
        return saved_paths
