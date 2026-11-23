#!/usr/bin/env python3
"""Preview or apply a local JSON export without replacing existing records."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STRING_FIELDS = {
    "title", "title_zh", "cover", "date", "director", "maker", "series",
    "shot", "subtitle", "url", "link", "linkType",
}
NUMBER_FIELDS = {
    "added_at", "comments", "likers", "lists", "people", "rawScore",
    "score", "size", "votes",
}
BOOLEAN_FIELDS = {"linkPending", "missing", "pending", "waiting"}


def code_key(value: str) -> str:
    return value.strip().upper()


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {} or (
        isinstance(value, str) and not value.strip()
    )


def parse_json(payload: bytes) -> Any:
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Invalid JSON number: {value}")

    return json.loads(payload.decode("utf-8-sig"),
                      object_pairs_hook=object_pairs, parse_constant=reject_constant)


def validate_item(item: Any, row: int, source: str) -> None:
    label = f"{source} row {row}"
    if not isinstance(item, dict):
        raise ValueError(f"{label}: expected an object")
    if not isinstance(item.get("code"), str) or not item["code"].strip():
        raise ValueError(f"{label}: code must be a non-empty string")
    for field, value in item.items():
        if value is None:
            continue
        if field in STRING_FIELDS and not isinstance(value, str):
            raise ValueError(f"{label}: {field} must be a string or null")
        if field in NUMBER_FIELDS and (
            type(value) not in (int, float)
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            raise ValueError(f"{label}: {field} must be a finite number or null")
        if field in BOOLEAN_FIELDS and not isinstance(value, bool):
            raise ValueError(f"{label}: {field} must be a boolean or null")
        if field in {"actors", "links", "pending_links", "genres"}:
            if not isinstance(value, list):
                raise ValueError(f"{label}: {field} must be an array or null")
            allowed = (str, int) if field == "genres" else (str,)
            if any(type(entry) not in allowed for entry in value):
                raise ValueError(f"{label}: invalid entry in {field}")
    if set(item.get("pending_links") or []) - set(item.get("links") or []) - {
        item.get("link")
    }:
        raise ValueError(f"{label}: pending_links contains a link missing from links")


def export_items(document: Any) -> list[dict[str, Any]]:
    items = document.get("items") if isinstance(document, dict) else document
    if not isinstance(items, list):
        raise ValueError("Export must be an array or an object containing an items array")
    for row, item in enumerate(items, 1):
        validate_item(item, row, "Export")
    return items


def normalized_item(item: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(item)
    result["code"] = code_key(item["code"])
    links = list(dict.fromkeys(result.get("links") or []))
    pending = list(dict.fromkeys(result.get("pending_links") or []))
    legacy = result.get("link")
    if legacy:
        if legacy not in links:
            links.append(legacy)
        if item.get("pending_links") is None and result.get("linkPending") and legacy not in pending:
            pending.append(legacy)
    result["links"] = links
    result["pending_links"] = pending
    return result


def merge_item(current: dict[str, Any], incoming: dict[str, Any],
               conflicts: list[dict[str, Any]], scope: str = "existing"
               ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = deepcopy(current)
    changed = []

    def merge(old, new, field):
        if is_empty(new) or old == new:
            return old
        if is_empty(old):
            changed.append({"field": field, "before": deepcopy(old), "after": deepcopy(new)})
            return deepcopy(new)
        if isinstance(old, dict) and isinstance(new, dict):
            value = deepcopy(old)
            for key, entry in new.items():
                if not is_empty(entry):
                    value[key] = merge(value.get(key), entry, f"{field}.{key}")
            return value
        if isinstance(old, list) and isinstance(new, list):
            value = deepcopy(old)
            for entry in new:
                if entry not in value:
                    value.append(deepcopy(entry))
            if value != old:
                changed.append({"field": field, "before": deepcopy(old), "after": deepcopy(value)})
            return value
        conflicts.append({"code": code_key(current["code"]), "field": field, "scope": scope,
                          "kept": deepcopy(old), "incoming": deepcopy(new)})
        return old

    for field, value in incoming.items():
        if field not in {"code", "pending_links"} and not is_empty(value):
            result[field] = merge(result.get(field), value, field)

    old_links = set(current.get("links") or [])
    old_pending = current.get("pending_links") or []
    new_pending = incoming.get("pending_links") or []
    common = old_links & set(incoming.get("links") or [])
    if (set(old_pending) & common) != (set(new_pending) & common):
        conflicts.append({"code": code_key(current["code"]), "field": "pending_links", "scope": scope,
                          "kept": sorted(set(old_pending) & common),
                          "incoming": sorted(set(new_pending) & common)})
    pending = list(old_pending)
    for link in new_pending:
        if link not in old_links and link not in pending:
            pending.append(link)
    if pending != old_pending:
        result["pending_links"] = pending
        changed.append({"field": "pending_links", "before": deepcopy(old_pending), "after": pending})
    return result, changed


def new_item(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    defaults = {
        **{field: "" for field in sorted(STRING_FIELDS)},
        **{field: 0 for field in sorted(NUMBER_FIELDS)},
        **{field: False for field in sorted(BOOLEAN_FIELDS)},
        "actors": [], "genres": [], "links": [], "pending_links": [],
        "score": None, "rawScore": None, "pending": True,
        "added_at": int(now.timestamp() * 1000),
    }
    defaults.update({key: deepcopy(value) for key, value in item.items()
                     if value is not None})
    return defaults


def merge_documents(target: Any, incoming: Any,
                    now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(target, dict) or not isinstance(target.get("items"), list):
        raise ValueError("Target must be an object containing an items array")
    result = deepcopy(target)
    positions = {}
    for row, item in enumerate(result["items"], 1):
        validate_item(item, row, "Target")
        key = code_key(item["code"])
        if key in positions:
            raise ValueError(f"Target contains duplicate code {key}; no changes applied")
        positions[key] = row - 1

    source_items = export_items(incoming)
    report = {"added_codes": [], "updated": [], "unchanged_codes": [],
              "local_only_codes": [], "duplicates": [], "conflicts": [],
              "ignored_root_fields": sorted(set(incoming) - {"items"})
              if isinstance(incoming, dict) else []}
    unique = {}
    rows = {}
    for row, item in enumerate(source_items, 1):
        item = normalized_item(item)
        key = item["code"]
        rows.setdefault(key, []).append(row)
        if key in unique:
            unique[key], _ = merge_item(unique[key], item, report["conflicts"], "import_duplicates")
        else:
            unique[key] = item
    report["duplicates"] = [{"code": key, "rows": value}
                            for key, value in rows.items() if len(value) > 1]
    report["local_only_codes"] = [key for key in positions if key not in unique]
    for key, item in unique.items():
        if key not in positions:
            result["items"].append(new_item(item, now))
            report["added_codes"].append(key)
            continue
        index = positions[key]
        merged, changes = merge_item(result["items"][index], item, report["conflicts"])
        if changes:
            result["items"][index] = merged
            report["updated"].append({"code": key, "fields": [entry["field"] for entry in changes],
                                      "changes": changes})
        else:
            report["unchanged_codes"].append(key)
    report["counts"] = {
        "existing": len(target["items"]), "import_rows": len(source_items),
        "import_unique": len(unique), "duplicate_rows": len(source_items) - len(unique),
        "added": len(report["added_codes"]), "updated": len(report["updated"]),
        "unchanged": len(report["unchanged_codes"]),
        "conflicts": len(report["conflicts"]), "result": len(result["items"]),
    }
    if report["added_codes"] or report["updated"]:
        result["updated_at"] = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return result, report


def apply_import(target: Path, original: bytes, document: dict[str, Any]) -> Path:
    backup_dir = ROOT / "work/import-backups"
    payload = json.dumps(document, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if target.read_bytes() != original:
            raise ValueError("Target changed during import; no changes applied. Run preview again")
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with tempfile.NamedTemporaryFile(dir=backup_dir, prefix=f"{target.stem}-{stamp}-",
                                         suffix=".json", delete=False) as backup:
            backup.write(original)
            backup.flush()
            os.fsync(backup.fileno())
            backup_path = Path(backup.name)
        os.chmod(temporary, target.stat().st_mode & 0o777)
        os.replace(temporary, target)
        return backup_path
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local JSON export")
    parser.add_argument("--target", type=Path, default=ROOT / "data/movies.json")
    parser.add_argument("--report", type=Path, help="Write the full comparison report as JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Back up and write merged data")
    mode.add_argument("--dry-run", action="store_true", help="Preview only (the default)")
    args = parser.parse_args(argv)
    report = None
    try:
        source, target = args.source.resolve(), args.target.resolve()
        report_path = args.report.resolve() if args.report else None
        if report_path in {source, target}:
            raise ValueError("Report path must differ from source and target")
        original = target.read_bytes()
        current = parse_json(original)
        merged, report = merge_documents(current, parse_json(source.read_bytes()),
                                         datetime.now(timezone.utc))
        report.update({"source": str(source), "target": str(target),
                       "mode": "apply" if args.apply else "preview", "backup": None})
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            if report_path.is_dir():
                raise ValueError("Report path must be a file")
        if args.apply and (report["counts"]["added"] or report["counts"]["updated"]):
            report["backup"] = str(apply_import(target, original, merged))
        if report_path:
            report_path.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False,
                                               indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"mode": report["mode"], **report["counts"],
                          "backup": report["backup"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        if report and report["backup"]:
            print(f"Data applied; backup: {report['backup']}. Report failed: {error}", file=sys.stderr)
        else:
            print(f"Import failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
