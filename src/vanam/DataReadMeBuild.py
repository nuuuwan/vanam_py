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

    @staticmethod
    def _load_json(path: str) -> dict | None:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"Skipping {path}: {exc}")
            return None

    def _iter_identifications(self):
        """Yield parsed identification dicts."""
        for root, _, files in os.walk(DATA_IDENTIFICATIONS_DIR):
            for fname in sorted(files):
                if not fname.endswith(".json"):
                    continue
                data = self._load_json(os.path.join(root, fname))
                if data is not None:
                    yield data

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
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        image_hash = ident.get("hash", "")
        results = ident.get("plantnet_data", {}).get("results", [])
        top = results[0] if results else {}
        species_data = top.get("species", {})

        species = species_data.get("scientificName", "—")
        confidence = self._format_confidence(top.get("score", 0))
        ut = self._format_timestamp(
            ident.get("image_metadata", {}).get("utImageTaken", "")
        )
        user = ident.get("image_metadata", {}).get("userId", "—")

        image_path = f"images/{image_hash[:4]}/{image_hash}.png"
        ident_path = f"identifications/{image_hash[:4]}/{image_hash}.json"
        thumbnail = (
            f'<a href="{image_path}"><img src="{image_path}" width="64"/></a>'
        )
        species_link = f"[*{species}*]({ident_path})"
        hash_link = f"[`{image_hash}`]({image_path})"

        return (
            f"| {thumbnail} "
            f"| {species_link} "
            f"| {confidence} "
            f"| {ut} "
            f"| `{user}` "
            f"| {hash_link} |"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def _build_table_lines(self, identifications: list) -> list[str]:
        lines = [
            "| Image | Species | Confidence | Time Taken | User | Image Hash |",
            "|---|---|---|---|---|---|",
        ]
        for ident in identifications:
            lines.append(self._render_row(ident))
        return lines

    def run(self) -> str:
        """Build and write data/README.md. Returns the output path."""
        identifications = list(self._iter_identifications())
        identifications.sort(
            key=lambda x: int(
                x.get("image_metadata", {}).get("utImageTaken", 0) or 0
            ),
            reverse=True,
        )

        data_size = self._data_dir_size()
        n = len(identifications)

        lines = [
            "# Vanam - Data\n",
            self._top_badges(data_size),
            f"**{n}** plant identification(s), "
            f"sorted by most recently photographed.\n",
        ]
        lines += self._build_table_lines(identifications)
        lines.append(self._bottom_badges())

        content = "\n".join(lines)
        os.makedirs(os.path.dirname(DATA_README_PATH), exist_ok=True)
        with open(DATA_README_PATH, "w", encoding="utf-8") as f:
            f.write(content)

        log.info(f"Written → {DATA_README_PATH}")
        return DATA_README_PATH
