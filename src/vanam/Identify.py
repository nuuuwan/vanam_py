import json
import os
import re

import requests
from utils import Log

log = Log(__name__)

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
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

    def _call_plantnet(self, photo_path: str) -> list[dict]:
        """Submit a photo to PlantNet and return a list of predictions
        in the project's canonical format."""
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

        predictions = []
        for result in raw.get("results", []):
            species = result.get("species", {})
            gbif = species.get("gbif") or {}
            iucn = species.get("iucn") or {}
            predictions.append(
                {
                    "confidence": round(result.get("score", 0), 5),
                    "species": species.get("scientificName", ""),
                    "genus": species.get("genus", {}).get(
                        "scientificNameWithoutAuthor", ""
                    ),
                    "family": species.get("family", {}).get(
                        "scientificNameWithoutAuthor", ""
                    ),
                    "commonNames": species.get("commonNames", []),
                    "gbifId": str(gbif.get("id", "")),
                    "iucnId": str(iucn.get("id", "")),
                    "iucnCategory": iucn.get("category", ""),
                }
            )
        return predictions

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
            photo_path = os.path.join(DATA_IMAGES_DIR, stem[:4], f"{stem}.png")
            if not os.path.exists(photo_path):
                log.debug(f"Photo not found on disk: {photo_path}")
                continue

            log.info(f"Identifying {stem} …")
            try:
                meta = self._load_image_metadata(stem)
                predictions = self._call_plantnet(photo_path)
            except requests.HTTPError as exc:
                log.warning(f"PlantNet error for {stem}: {exc}")
                continue

            location = meta.get("imageLocation", {})
            identification = {
                "imageHash": stem,
                "imageLocation": {
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "accuracy": location.get("accuracy"),
                    "source": location.get("source", "image-metadata"),
                },
                "utImageTaken": meta.get("utImageTaken"),
                "userId": meta.get("userId"),
                "deviceIPAddress": meta.get("deviceIPAddress"),
                "plantNetPredictions": predictions,
            }

            saved_paths.append(self._save(stem, identification))

        log.info(f"Done. {len(saved_paths)} identification(s) saved.")
        return saved_paths
