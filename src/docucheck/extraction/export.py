"""Public receipt output, kept separate from diagnostic extraction records."""

from pathlib import Path

from .qwen import FIELDS, write_json


def export_receipts(results: list[dict], directory: Path) -> None:
    """Write one four-field JSON per receipt; unresolved values remain null."""
    for result in results:
        fields = result.get("fields", {})
        receipt = {
            field: fields.get(field, {}).get("value_normalized") for field in FIELDS
        }
        write_json(directory / "receipts" / f"{result['image_id']}.json", receipt)
