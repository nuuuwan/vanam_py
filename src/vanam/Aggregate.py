import datetime
import json
import os

from utils import Log

log = Log(__name__)

DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
DATA_AGGREGATED_DIR = os.path.join("data", "aggregated")


class Aggregate:
    """Reads all identification JSONs and produces two aggregated files:

    - data/aggregated/user_map.json  — maps userId → [imageHash, ...]
    - data/aggregated/all.json       — list of identification summaries
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: str) -> dict | None:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"Skipping {path}: {exc}")
            return None

    def _iter_identifications(self):
        """Yield parsed identification dicts from data/identifications."""
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in sorted(files):
                if not fname.endswith(".json"):
                    continue
                data = self._load_json(os.path.join(root, fname))
                if data is not None:
                    yield data

    PREDICTION_CONFIDENCE_THRESHOLD = 0.10

    @staticmethod
    def _parse_result(result: dict) -> dict:
        species = result.get("species", {})
        gbif = result.get("gbif") or {}
        iucn = result.get("iucn") or {}
        powo = result.get("powo") or {}
        return {
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
            "powoId": str(powo.get("id", "")),
        }

    def _predictions(self, identification: dict) -> list[dict]:
        results = identification.get("plantnet_data", {}).get("results", [])
        if not results:
            return []
        parsed = []
        for i, r in enumerate(results):
            if (
                i == 0
                or r.get("score", 0) > self.PREDICTION_CONFIDENCE_THRESHOLD
            ):
                parsed.append(self._parse_result(r))
        return parsed

    @staticmethod
    def _write_json(path: str, data) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"Written → {path}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Build and save user_map.json and all.json."""
        user_map: dict[str, list[str]] = {}
        all_summaries: list[dict] = []

        for ident in self._iter_identifications():
            image_hash = ident.get("hash", "")
            image_meta = ident.get("image_metadata", {})
            location = image_meta.get("imageLocation", {})
            user_id = image_meta.get("userId")
            predictions = self._predictions(ident)
            nominatim_display_name = ident.get("nominatim_data", {}).get(
                "display_name"
            )

            # user_map
            if user_id:
                user_map.setdefault(user_id, []).append(image_hash)

            # all.json summary
            ut = image_meta.get("utImageTaken")
            try:
                time_taken = (
                    datetime.datetime.utcfromtimestamp(int(ut)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if ut is not None
                    else None
                )
            except (ValueError, OSError, OverflowError):
                time_taken = None
            all_summaries.append(
                {
                    "imageHash": image_hash,
                    "latLng": {
                        "lat": location.get("latitude"),
                        "lng": location.get("longitude"),
                    },
                    "source": location.get("source"),
                    "utImageTaken": ut,
                    "timeImageTaken": time_taken,
                    "userId": user_id,
                    "nominatim_display_name": nominatim_display_name,
                    "predictions": predictions,
                }
            )

        self._write_json(
            os.path.join(DATA_AGGREGATED_DIR, "user_map.json"),
            user_map,
        )
        self._write_json(
            os.path.join(DATA_AGGREGATED_DIR, "all.json"),
            all_summaries,
        )

        log.info(
            f"Aggregated {len(all_summaries)} identification(s) "
            f"across {len(user_map)} user(s)."
        )
