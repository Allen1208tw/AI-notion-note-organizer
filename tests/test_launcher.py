from __future__ import annotations

import unittest
from unittest.mock import patch

import launcher


class LauncherEnvironmentTests(unittest.TestCase):
    def test_missing_parent_package_is_reported_as_a_missing_dependency(self) -> None:
        with patch.object(
            launcher,
            "REQUIRED_MODULES",
            {"google.genai": "google-genai"},
        ):
            with patch.object(launcher, "APPLICATION_IMPORT_CHECKS", ()):
                with patch.object(
                    launcher.importlib.util,
                    "find_spec",
                    side_effect=ModuleNotFoundError("No module named 'google'"),
                ):
                    try:
                        errors = launcher._check_environment()
                    except ModuleNotFoundError as error:
                        self.fail(f"Environment check crashed: {error}")

        self.assertTrue(any("google-genai" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
