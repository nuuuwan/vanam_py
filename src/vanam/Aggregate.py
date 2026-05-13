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

    @staticmethod
    def _top_prediction(identification: dict) -> dict | None:
        predictions = identification.get("plantNetPredictions", [])
        return predictions[0] if predictions else None

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
            image_hash = ident.get("imageHash", "")
            location = ident.get("imageLocation", {})
            user_id = ident.get("userId")
            top = self._top_prediction(ident)

            # user_map
            if user_id:
                user_map.setdefault(user_id, []).append(image_hash)

            # all.json summary
            all_summaries.append(
                {
                    "imageHash": image_hash,
                    "latLng": {
                        "lat": location.get("latitude"),
                        "lng": location.get("longitude"),
                    },
                    "source": location.get("source"),
                    "utImageTaken": ident.get("utImageTaken"),
                    "userId": user_id,
                    "topPrediction": top,
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
