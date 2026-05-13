import datetime
import json
import os
import subprocess

from utils import Log

log = Log(__name__)

DATA_IDENTIFICATIONS_DIR = os.path.join("data", "identifications")
DATA_README_PATH = os.path.join("data", "README.md")


class DataReadMeBuild:
    """Generates data/README.md summarising all identified plants."""

    REPO_OWNER = "nuuuwan"
    REPO_NAME = "vanam_py"
    LICENSE = "MIT"
    LANGUAGE = "Python"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_identifications(self):
        """Yield parsed identification dicts."""
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in sorted(files):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, encoding="utf-8") as f:
                        yield json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    log.warning(f"Skipping {path}: {exc}")

    @staticmethod
    def _data_dir_size() -> str:
        """Return human-readable size of the data/ directory."""
        try:
            result = subprocess.run(
                ["du", "-sh", "data"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.split()[0]
        except Exception:
            return "unknown"

    @staticmethod
    def _shield(label: str, message: str, color: str) -> str:
        """Return a shields.io badge in Markdown."""
        label_enc = label.replace(" ", "%20").replace("-", "--")
        message_enc = (
            message.replace(" ", "%20").replace("-", "--").replace("_", "__")
        )
        url = (
            f"https://img.shields.io/badge/"
            f"{label_enc}-{message_enc}-{color}"
        )
        return f"![{label}]({url})"

    def _top_badges(self, data_size: str) -> str:
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        updated = self._shield("updated", now, "blue")
        size = self._shield("data size", data_size, "lightgrey")
        return f"{updated}  {size}\n"

    def _bottom_badges(self) -> str:
        owner = self._shield("author", self.REPO_OWNER, "informational")
        license_badge = self._shield("license", self.LICENSE, "green")
        lang = self._shield("language", self.LANGUAGE, "yellow")
        return f"\n---\n\n{owner}  {license_badge}  {lang}\n"

    @staticmethod
    def _format_confidence(conf: float) -> str:
        return f"{conf * 100:.1f}%"

    @staticmethod
    def _format_timestamp(ut: str) -> str:
        try:
            dt = datetime.datetime.utcfromtimestamp(int(ut))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return ut

    def _render_row(self, ident: dict) -> str:
        image_hash = ident.get("imageHash", "")
        predictions = ident.get("plantNetPredictions", [])
        top = predictions[0] if predictions else {}

        species = top.get("species", "—")
        common = (top.get("commonNames") or ["—"])[0]
        confidence = self._format_confidence(top.get("confidence", 0))
        family = top.get("family", "—")
        loc = ident.get("imageLocation", {})
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        latlng = (
            f"{lat:.4f}, {lng:.4f}"
            if lat is not None and lng is not None
            else "—"
        )
        ut = self._format_timestamp(ident.get("utImageTaken", ""))
        user = ident.get("userId", "—")

        return (
            f"| `{image_hash}` "
            f"| *{species}* "
            f"| {common} "
            f"| {family} "
            f"| {confidence} "
            f"| {latlng} "
            f"| {ut} "
            f"| `{user}` |"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Build and write data/README.md. Returns the output path."""
        identifications = list(self._iter_identifications())

        # Sort descending by utImageTaken (string → int comparison)
        identifications.sort(
            key=lambda x: int(x.get("utImageTaken", 0) or 0),
            reverse=True,
        )

        data_size = self._data_dir_size()
        n = len(identifications)

        lines = []

        # Title
        lines.append("# Vanam - Data\n")

        # Badges below title
        lines.append(self._top_badges(data_size))

        lines.append(
            f"**{n}** plant identification(s), "
            f"sorted by most recently photographed.\n"
        )

        # Table
        lines.append(
            "| Image Hash | Species | Common Name | Family "
            "| Confidence | Location (lat, lng) "
            "| Time Taken | User |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for ident in identifications:
            lines.append(self._render_row(ident))

        # Bottom badges
        lines.append(self._bottom_badges())

        content = "\n".join(lines)
        os.makedirs(os.path.dirname(DATA_README_PATH), exist_ok=True)
        with open(DATA_README_PATH, "w", encoding="utf-8") as f:
            f.write(content)

        log.info(f"Written → {DATA_README_PATH}")
        return DATA_README_PATH
