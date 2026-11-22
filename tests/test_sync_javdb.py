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


if __name__ == "__main__":
    unittest.main()
