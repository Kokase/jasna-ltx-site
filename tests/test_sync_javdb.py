import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "sync_javdb", Path(__file__).resolve().parents[1] / "scripts/sync_javdb.py"
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class PosterTest(unittest.TestCase):
    def test_posters_preserve_original_aspect_ratio(self):
        from urllib.parse import parse_qs, urlsplit
        source = "https://c0.jdbstatic.com/covers/test.jpg"
        query = parse_qs(urlsplit(sync.proxy_wrap(source)).query)
        self.assertEqual(query["w"], ["800"])
        self.assertNotIn("h", query)
        self.assertEqual(query["u"], [source])

    def test_screenshot_size_is_preserved(self):
        source = "https://c0.jdbstatic.com/samples/test.jpg"
        self.assertIn("w=900", sync.proxy_wrap(source, w=900, h=None))


class BackfillTest(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.data = Path(directory) / "movies.json"
        self.data.write_text(json.dumps({"items": [
            {"code": f"TEST-{i:03}", "subtitle": "fixture.srt", "shot": ""}
            for i in range(5)
        ]}))
        self.enterContext(patch.object(sync, "DATA", str(self.data)))
        self.enterContext(patch.object(sync, "SUBCHK", str(Path(directory) / "checked.json")))
        self.enterContext(patch.object(sync, "candidate_ids", return_value=[]))
        self.enterContext(patch.object(sync.time, "sleep"))
        self.enterContext(patch.object(sys, "argv", ["sync_javdb.py", "--backfill", "2"]))

    def test_missing_images_do_not_exceed_probe_limit(self):
        with patch.object(sync, "find_shot", return_value="") as shots:
            self.assertEqual(sync.main(), 0)
        self.assertEqual(shots.call_count, 2)

    def test_image_only_changes_are_saved(self):
        with patch.object(sync, "find_shot", return_value="https://example.invalid/shot.jpeg"):
            self.assertEqual(sync.main(), 0)
        items = json.loads(self.data.read_text())["items"]
        self.assertEqual(sum(bool(item["shot"]) for item in items), 2)


class ExistingRecordTest(unittest.TestCase):
    def test_refresh_replaces_non_empty_fields_and_preserves_local_data(self):
        current = {"code": "TEST-001", "title": "Old", "cover": "old-image",
                   "actors": ["Old"], "link": "saved-file", "links": ["saved-file"],
                   "added_at": 123, "pending": False, "comments": 4, "score": 4.2}
        incoming = {"code": "TEST-001", "title": "New", "cover": "", "actors": ["New"],
                    "link": "", "links": [], "added_at": 999, "pending": True, "comments": 0, "score": 0}
        self.assertTrue(sync.update_existing(current, incoming))
        self.assertEqual(current, {"code": "TEST-001", "title": "New", "cover": "old-image",
                                  "actors": ["New"], "link": "saved-file", "links": ["saved-file"],
                                  "added_at": 123, "pending": False, "comments": 4, "score": 4.2})
        self.assertFalse(sync.update_existing(current, incoming))

    def test_existing_only_refresh_is_saved_without_duplicate_or_new_record(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "movies.json"
            data.write_text(json.dumps({"items": [{"code": "test-001", "title": "Old", "added_at": 123}]}))
            with patch.object(sync, "DATA", str(data)), \
                 patch.object(sync, "candidate_ids", return_value=["fixture"]), \
                 patch.object(sync, "fetch", return_value=("fixture", "https://example.invalid")), \
                 patch.object(sync, "parse_detail", return_value={"code": "TEST-001", "title": "New"}), \
                 patch.object(sys, "argv", ["sync_javdb.py", "--backfill", "0", "--overwrite-existing"]):
                self.assertEqual(sync.main(), 0)
            items = json.loads(data.read_text())["items"]
            self.assertEqual(items, [{"code": "test-001", "title": "New", "added_at": 123}])


if __name__ == "__main__":
    unittest.main()
