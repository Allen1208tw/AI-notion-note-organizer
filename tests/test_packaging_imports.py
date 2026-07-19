from __future__ import annotations

import importlib
import unittest

from launcher import APPLICATION_IMPORT_CHECKS


class PackagingImportTests(unittest.TestCase):
    def test_all_runtime_modules_can_be_imported(self) -> None:
        failures = []
        for module_name in APPLICATION_IMPORT_CHECKS:
            try:
                importlib.import_module(module_name)
            except Exception as error:
                failures.append(f"{module_name}: {error}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
