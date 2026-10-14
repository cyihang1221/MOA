"""从服务器本地路径导入数据：硬链接、不经浏览器上传。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.session_storage import (
    import_files_into_upload_dir,
    collect_importable_files,
)


class ImportServerPathTests(unittest.TestCase):
    def test_hardlink_raw_into_session_raw_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "data"
            src_dir.mkdir()
            src = src_dir / "BK-1.raw"
            src.write_bytes(b"raw-bytes")
            dest_root = root / "session"
            dest_root.mkdir()
            saved = import_files_into_upload_dir(dest_root, src_dir)
            self.assertEqual(len(saved), 1)
            dest = dest_root / "raw" / "BK-1.raw"
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes(), b"raw-bytes")
            self.assertEqual(src.stat().st_ino, dest.stat().st_ino)

    def test_collect_nested_mzml(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b"
            nested.mkdir(parents=True)
            (nested / "QC-1.mzML").write_text("mzml")
            (Path(tmp) / "notes.txt").write_text("skip-or-keep")
            files = collect_importable_files(Path(tmp))
            names = {p.name for p in files}
            self.assertIn("QC-1.mzML", names)
            self.assertIn("notes.txt", names)


if __name__ == "__main__":
    unittest.main()
