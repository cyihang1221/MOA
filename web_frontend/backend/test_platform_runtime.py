"""运行时检测：Rscript / ThermoRawFileParser 应跟当前 Python 环境走。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.platform_utils import check_agent_runtime, resolve_rscript, resolve_thermo_rawfile_parser


class PlatformRuntimeTests(unittest.TestCase):
    def test_rscript_found_beside_moa_python(self):
        path = resolve_rscript()
        self.assertTrue(Path(path).is_file(), path)
        self.assertIn("Rscript", Path(path).name)

    def test_runtime_reports_r_available(self):
        info = check_agent_runtime()
        self.assertTrue(info["r_available"], info.get("issues"))
        parser = resolve_thermo_rawfile_parser()
        if parser:
            self.assertEqual(
                info["preferred_raw_converter"]["tool"],
                "convert_raw_to_mzml_ThermoRawFileParser",
            )


if __name__ == "__main__":
    unittest.main()
