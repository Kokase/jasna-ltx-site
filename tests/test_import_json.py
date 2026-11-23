from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "import_json", Path(__file__).resolve().parents[1] / "scripts/import_json.py"
)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)
NOW = datetime(2026, 11, 23, 5, 0, tzinfo=timezone.utc)


class MergeTest(unittest.TestCase):
    def test_deduplicates_import_and_preserves_local_records_and_metadata(self):
        target = {"items": [{"code": "local-001", "title": "Local title"}],
                  "avatars": {"Local": "local.jpg"}, "updated_at": "old"}
        incoming = {"items": [{"code": " demo-001 ", "title": "First title"},
                              {"code": "DEMO-001", "title": "Other title", "maker": "Studio"}],
                    "avatars": {"External": "external.jpg"}}
        saved_target, saved_incoming = deepcopy(target), deepcopy(incoming)
        result, report = importer.merge_documents(target, incoming, NOW)
        self.assertEqual([item["code"] for item in result["items"]], ["local-001", "DEMO-001"])
        self.assertEqual(result["items"][0], target["items"][0])
        self.assertEqual(result["items"][1]["title"], "First title")
        self.assertEqual(result["items"][1]["maker"], "Studio")
        self.assertEqual(result["avatars"], target["avatars"])
        self.assertEqual(report["added_codes"], ["DEMO-001"])
        self.assertEqual(report["local_only_codes"], ["LOCAL-001"])
        self.assertEqual(report["duplicates"], [{"code": "DEMO-001", "rows": [1, 2]}])
        self.assertEqual(report["ignored_root_fields"], ["avatars"])
        self.assertEqual(report["counts"]["duplicate_rows"], 1)
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertEqual(target, saved_target)
        self.assertEqual(incoming, saved_incoming)

    def test_fills_empty_values_and_extends_arrays_without_overwriting_zero_or_false(self):
        target = {"items": [{"code": "Demo-001", "title": "Kept", "title_zh": " ",
                             "score": 0, "pending": False, "actors": ["A"],
                             "custom": {"kept": "Local", "empty": None}}]}
        incoming = [{"code": "demo-001", "title": "External", "title_zh": "Translation",
                     "score": 5, "pending": True, "actors": ["A", "B"],
                     "custom": {"kept": "External", "empty": "Filled", "blank": None}}]
        result, report = importer.merge_documents(target, incoming, NOW)
        item = result["items"][0]
        self.assertEqual(item["code"], "Demo-001")
        self.assertEqual(item["title"], "Kept")
        self.assertEqual(item["title_zh"], "Translation")
        self.assertEqual(item["score"], 0)
        self.assertFalse(item["pending"])
        self.assertEqual(item["actors"], ["A", "B"])
        self.assertEqual(item["custom"], {"kept": "Local", "empty": "Filled"})
        self.assertEqual(report["counts"]["updated"], 1)
        self.assertEqual({entry["field"] for entry in report["conflicts"]},
                         {"title", "score", "pending", "custom.kept"})

    def test_keeps_confirmation_of_existing_links_and_imports_state_of_new_links(self):
        target = {"items": [{"code": "DEMO-001", "links": ["confirmed", "pending"],
                             "pending_links": ["pending"]}]}
        incoming = [{"code": "DEMO-001", "links": ["confirmed", "pending", "new", "new"],
                     "pending_links": ["confirmed", "new"]}]
        result, report = importer.merge_documents(target, incoming, NOW)
        self.assertEqual(result["items"][0]["links"], ["confirmed", "pending", "new"])
        self.assertEqual(result["items"][0]["pending_links"], ["pending", "new"])
        self.assertEqual(report["conflicts"][0]["field"], "pending_links")
        self.assertIn({"field": "links", "before": ["confirmed", "pending"],
                       "after": ["confirmed", "pending", "new"]},
                      report["updated"][0]["changes"])

    def test_accepts_legacy_single_link_and_supplies_required_site_fields(self):
        source = [{"code": "DEMO-001", "link": "https://example.invalid/file",
                   "links": ["https://example.invalid/file"],
                   "linkPending": True, "actors": None, "score": None}]
        result, _ = importer.merge_documents({"items": []}, source, NOW)
        item = result["items"][0]
        self.assertEqual(item["links"], ["https://example.invalid/file"])
        self.assertEqual(item["pending_links"], item["links"])
        self.assertEqual(item["actors"], [])
        self.assertEqual(item["genres"], [])
        self.assertIsNone(item["score"])
        self.assertIsInstance(item["url"], str)
        self.assertIsInstance(item["title"], str)
        self.assertTrue(item["pending"])
        self.assertEqual(item["added_at"], int(NOW.timestamp() * 1000))

    def test_reimport_is_idempotent_and_does_not_change_update_timestamp(self):
        source = [{"code": "DEMO-001", "title": "First", "actors": ["A"]}]
        first, _ = importer.merge_documents({"items": []}, source, NOW)
        second, report = importer.merge_documents(first, source, datetime.now(timezone.utc))
        self.assertEqual(second, first)
        self.assertEqual(report["counts"]["added"], 0)
        self.assertEqual(report["counts"]["updated"], 0)
        self.assertEqual(report["unchanged_codes"], ["DEMO-001"])

    def test_explicit_per_link_state_takes_precedence_over_legacy_summary_flag(self):
        item = {"code": "DEMO-001", "links": ["existing"], "pending_links": [],
                "link": "existing", "linkPending": True}
        target = {"items": [item]}
        result, report = importer.merge_documents(target, [item], NOW)
        self.assertEqual(result, target)
        self.assertEqual(report["conflicts"], [])

    def test_fill_empty_only_preserves_nonempty_arrays_and_link_states(self):
        old = {"code": "DEMO-001", "actors": ["A"], "links": ["existing"],
               "pending_links": [], "maker": "", "score": 0, "pending": False}
        source = [{"code": "DEMO-001", "actors": ["A", "B"],
                   "links": ["existing", "new"], "pending_links": ["new"],
                   "maker": "Studio", "score": 5, "pending": True}]
        result, report = importer.merge_documents({"items": [old]}, source, NOW,
                                                   fill_empty_only=True)
        self.assertEqual(result["items"][0], {**old, "maker": "Studio"})
        self.assertEqual(report["updated"][0]["fields"], ["maker"])

    def test_fill_empty_only_still_fills_empty_arrays(self):
        result, _ = importer.merge_documents({"items": [{"code": "DEMO-001", "actors": []}]},
                                              [{"code": "DEMO-001", "actors": ["A"]}],
                                              NOW, fill_empty_only=True)
        self.assertEqual(result["items"][0]["actors"], ["A"])

    def test_raw_score_only_new_record_has_compatible_score(self):
        result, _ = importer.merge_documents({"items": []},
                                              [{"code": "DEMO-001", "rawScore": 4.2}], NOW)
        self.assertEqual(result["items"][0]["score"], 4.2)
        self.assertEqual(result["items"][0]["rawScore"], 4.2)

    def test_does_not_guess_hyphens_or_remove_leading_zeroes(self):
        result, _ = importer.merge_documents({"items": []},
                                             [{"code": code} for code in
                                              ["DEMO001", "DEMO-001", "DEMO-1"]], NOW)
        self.assertEqual(len(result["items"]), 3)

    def test_rejects_invalid_rows_and_existing_duplicate_codes(self):
        for source in [{"data": []}, [None], [{"code": " "}], [{"code": 123}],
                       [{"code": "X", "actors": "A"}], [{"code": "X", "score": True}],
                       [{"code": "X", "pending": 1}], [{"code": "X", "links": [123]}],
                       [{"code": "X", "pending_links": ["orphan"]}]]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                importer.merge_documents({"items": []}, source, NOW)
        with self.assertRaisesRegex(ValueError, "duplicate code"):
            importer.merge_documents({"items": [{"code": "x"}, {"code": " X "}]}, [], NOW)


class ImportCliTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.target = self.directory / "movies.json"
        self.source = self.directory / "export.json"
        self.report = self.directory / "report.json"
        self.original = b'{"items": [{"code":"LOCAL-001","title":"Local"}],"custom":true}\n'
        self.target.write_bytes(self.original)
        self.source.write_text(json.dumps({"items": [{"code": "NEW-001"}]}))
        self.enterContext(patch.object(importer, "ROOT", self.directory))
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.enterContext(redirect_stdout(self.stdout))
        self.enterContext(redirect_stderr(self.stderr))

    def run_import(self, *args):
        return importer.main([str(self.source), "--target", str(self.target),
                              "--report", str(self.report), *args])

    def test_default_preview_reports_differences_without_touching_data_or_backups(self):
        source = self.source.read_bytes()
        self.assertEqual(self.run_import(), 0)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(self.source.read_bytes(), source)
        self.assertFalse((self.directory / "work").exists())
        report = json.loads(self.report.read_text())
        self.assertEqual(report["mode"], "preview")
        self.assertEqual(report["added_codes"], ["NEW-001"])
        self.assertEqual(report["local_only_codes"], ["LOCAL-001"])
        self.assertIsNone(report["backup"])

    def test_apply_backs_up_exact_bytes_and_reimport_does_not_write_or_back_up_again(self):
        self.assertEqual(self.run_import("--apply"), 0)
        report = json.loads(self.report.read_text())
        backup = Path(report["backup"])
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(backup.parent, self.directory / "work/import-backups")
        data = json.loads(self.target.read_text())
        self.assertTrue(data["custom"])
        self.assertEqual(len(data["items"]), 2)
        applied = self.target.read_bytes()
        self.assertEqual(self.run_import("--apply"), 0)
        self.assertEqual(self.target.read_bytes(), applied)
        self.assertIsNone(json.loads(self.report.read_text())["backup"])
        self.assertEqual(len(list(backup.parent.iterdir())), 1)

    def test_rejects_malformed_json_and_invalid_late_rows_without_partial_writes(self):
        for payload in ['{', '{"items":[],"items":[]}',
                        '[{"code":"NEW-001","score":NaN}]',
                        '[{"code":"NEW-001"},{"code":""}]']:
            with self.subTest(payload=payload):
                self.source.write_text(payload)
                self.assertEqual(self.run_import("--apply"), 1)
                self.assertEqual(self.target.read_bytes(), self.original)
                self.assertFalse((self.directory / "work").exists())

    def test_report_cannot_replace_either_input_file(self):
        for path in [self.source, self.target]:
            with self.subTest(path=path):
                self.report = path
                before = path.read_bytes()
                self.assertEqual(self.run_import("--apply"), 1)
                self.assertEqual(path.read_bytes(), before)

    def test_invalid_report_directory_does_not_apply_changes(self):
        self.report = self.directory
        self.assertEqual(self.run_import("--apply"), 1)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse((self.directory / "work").exists())

    def test_report_failure_after_apply_reports_that_data_was_applied(self):
        with patch.object(Path, "write_text", side_effect=PermissionError("Report blocked")):
            self.assertEqual(self.run_import("--apply"), 1)
        self.assertEqual(len(json.loads(self.target.read_text())["items"]), 2)
        self.assertIn("Data applied; backup:", self.stderr.getvalue())
        self.assertIn("Report failed: Report blocked", self.stderr.getvalue())

    def test_concurrent_target_change_is_not_overwritten(self):
        newer = b'{"items":[{"code":"NEWER-001"}]}'
        self.target.write_bytes(newer)
        with self.assertRaisesRegex(ValueError, "changed during import"):
            importer.apply_import(self.target, self.original, {"items": []})
        self.assertEqual(self.target.read_bytes(), newer)
        self.assertFalse((self.directory / "work").exists())
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"movies.json", "export.json"})

    def test_backup_failure_keeps_target_and_cleans_temporary_file(self):
        (self.directory / "work").write_text("not a directory")
        self.assertEqual(self.run_import("--apply"), 1)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual({p.name for p in self.directory.iterdir()},
                         {"movies.json", "export.json", "work"})

    def test_utf8_bom_export_is_accepted(self):
        self.source.write_text('[{"code":"NEW-001"}]', encoding="utf-8-sig")
        self.assertEqual(self.run_import(), 0)

    def test_supplied_images_and_links_fill_empty_fields_without_overwriting_existing_values(self):
        current = {"items": [{"code": "LOCAL-001", "title": "Local", "cover": "",
                              "links": [], "pending_links": []}]}
        self.target.write_text(json.dumps(current))
        self.source.write_text(json.dumps({"items": [{"code": "LOCAL-001", "title": "Other",
            "cover": "https://example.invalid/image.jpg", "links": ["https://example.invalid/file"]}]}))
        self.assertEqual(self.run_import("--apply", "--fill-empty-only"), 0)
        result = json.loads(self.target.read_text())["items"][0]
        self.assertEqual(result["title"], "Local")
        self.assertEqual(result["cover"], "https://example.invalid/image.jpg")
        self.assertEqual(result["links"], ["https://example.invalid/file"])


if __name__ == "__main__":
    unittest.main()
