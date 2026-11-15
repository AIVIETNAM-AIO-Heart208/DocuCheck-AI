"""Lossless table serialization for oversized refined requests."""
from copy import deepcopy
import json


class ContextBudgetExceeded(ValueError):
    """All evidence is retained, but the request still cannot fit."""


def table_data(data):
    """Remove repeated JSON keys and label text already present in regions.

    Candidate value text stays explicit (a scalar can be a substring of a region).
    No candidate, source region, role hypothesis or geometry hint is filtered.
    """
    result = deepcopy(data)
    tables = {
        "regions": ("id", "text", "bbox"),
        "optional_text_parts": ("id", "region_id", "text"),
        "lines": ("id", "regions", "block"),
        "blocks": ("id", "lines", "ambiguous"),
    }
    for name, columns in tables.items():
        result[name] = {"columns": list(columns),
                        "rows": [[row[col] for col in columns] for row in data[name]]}
    columns = ["id", "regions", "text", "label_region_ids", "label_alternatives", "role_hypotheses"]
    result["candidates"] = {
        field: {"columns": columns, "rows": [
            [c["id"], c["regions"], c["text"],
             [label["region_id"] for label in c["labels"]],
             c["label_alternatives"], c["role_hypotheses"]] for c in values]}
        for field, values in data["candidates"].items()}
    # Label references are lossless only when they refer to complete region text.
    sources = {r["id"]: r["text"] for r in data["regions"]}
    result["scoped_label_text"] = [
        [field, c["id"], label["region_id"], label["text"]]
        for field, values in data["candidates"].items() for c in values
        for label in c["labels"] if sources.get(label["region_id"]) != label["text"]]
    result["table_encoding"] = (
        "Each table row follows its columns. label_region_ids reference region text; "
        "scoped_label_text overrides a label for that field/candidate. IDs and selection schema unchanged.")
    return result


def fit_request(client, payload, data):
    """Tokenize at most twice; never call generation or truncate evidence."""
    attempts = []
    for version in ("readable_text_ids_v3", "tables_v1"):
        if version == "tables_v1":
            payload["messages"][1]["content"] = json.dumps(table_data(data), ensure_ascii=False, separators=(",", ":"))
        formatted = client.request("/apply-template", {"messages": payload["messages"]})
        tokens = client.request("/tokenize", {"content": formatted["prompt"], "add_special": True})["tokens"]
        attempts.append({"version": version, "prompt_tokens": len(tokens)})
        if len(tokens) + payload["max_tokens"] <= client.context:
            break
    return tokens, attempts
