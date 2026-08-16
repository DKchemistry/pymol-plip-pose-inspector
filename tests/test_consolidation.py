from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from pymol.Qt import QtCore
except ImportError:
    QtCore = None


class MemorySettings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None, **_kwargs):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


@unittest.skipIf(QtCore is None, "PyMOL Qt is not installed in this Python")
class ConsolidationTests(unittest.TestCase):
    def test_combined_health_check_requires_all_engines(self):
        from pymol_plip.runtime import WorkerRuntime

        settings = MemorySettings()
        runtime = WorkerRuntime(settings)
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "python"
            executable.write_text("placeholder", encoding="utf-8")
            settings.setValue("worker_python", str(executable))
            event = {
                "event": "health",
                "ok": True,
                "engine": {
                    "python": "3.12.0",
                    "plip": "3.0.1",
                    "openbabel": "3.2.1",
                    "rdkit": "2025.03.5",
                },
            }
            completed = SimpleNamespace(
                returncode=0, stdout=json.dumps(event) + "\n", stderr=""
            )
            with mock.patch("pymol_plip.runtime.subprocess.run", return_value=completed):
                ok, message, engine = runtime.health_check(executable)
        self.assertTrue(ok)
        self.assertIn("RDKit 2025.03.5", message)
        self.assertEqual(engine["plip"], "3.0.1")

    def test_new_environment_precedes_legacy_candidates(self):
        from pymol_plip.runtime import WorkerRuntime

        runtime = WorkerRuntime(MemorySettings())
        candidates = [str(path) for path in runtime.worker_python_candidates()]
        unified = next(
            index for index, value in enumerate(candidates)
            if "/envs/pymol-pose-inspector/bin/python" in value
        )
        legacy = [
            index for index, value in enumerate(candidates)
            if "/envs/pymol-plip-plugin/bin/python" in value
            or "/envs/pymol-ligand-review/bin/python" in value
        ]
        self.assertTrue(all(unified < index for index in legacy))

    def test_application_controllers_share_one_state_timer(self):
        from pymol import cmd
        from pymol_plip.application import PoseInspectorApplication

        cmd.reinitialize()
        application = PoseInspectorApplication(cmd)
        try:
            self.assertIs(
                application.plip_controller.state_timer,
                application.review_controller.state_timer,
            )
            self.assertIs(
                application.session.state_timer,
                application.plip_controller.state_timer,
            )
        finally:
            application.session.state_timer.stop()


if __name__ == "__main__":
    unittest.main()
