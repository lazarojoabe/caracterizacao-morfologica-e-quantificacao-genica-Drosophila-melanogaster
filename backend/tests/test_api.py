from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.services.session_manager import SessionManager


class ApiTests(unittest.TestCase):
    def test_upload_edit_and_path_sanitization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = SessionManager(Path(temporary))
            nucleus = np.zeros((64, 64), np.uint8); cv2.circle(nucleus, (32, 32), 15, 255, -1)
            protein = np.full((64, 64), 8, np.uint8); protein[nucleus > 0] = 100
            encode = lambda image: cv2.imencode(".png", image)[1].tobytes()
            with patch.object(main, "manager", manager):
                with TestClient(main.app) as client:
                    response = client.post(
                        "/api/sessions",
                        data={"config_json": json.dumps({"min_nucleus_area": 20, "protein_channel": 0})},
                        files={
                            "nucleus_file": ("../nucleus.png", encode(nucleus), "image/png"),
                            "protein_file": ("protein.png", encode(protein), "image/png"),
                        },
                    )
                    self.assertEqual(response.status_code, 202, response.text)
                    session = response.json()
                    for _ in range(20):
                        result = client.get(f"/api/sessions/{session['session_id']}/result").json()
                        if result["status"] == "ready":
                            break
                        time.sleep(0.02)
                    self.assertEqual(result["nuclei"][0]["state"], "active")
                    edited = client.post(f"/api/sessions/{session['session_id']}/edits", json={"operation": "exclude", "nucleus_ids": [1], "base_revision": 0})
                    self.assertEqual(edited.status_code, 200, edited.text)
                    self.assertEqual(edited.json()["aggregate"]["nucleus_count"], 0)
                    conflict = client.post(f"/api/sessions/{session['session_id']}/edits", json={"operation": "restore", "nucleus_ids": [1], "base_revision": 0})
                    self.assertEqual(conflict.status_code, 409)
                    multichannel = client.post(
                        "/api/sessions",
                        data={"config_json": json.dumps({"min_nucleus_area": 20, "nucleus_channel": 0, "protein_channel": 0})},
                        files={"nucleus_file": ("channels.png", encode(protein), "image/png")},
                    )
                    self.assertEqual(multichannel.status_code, 202, multichannel.text)
            manager.executor.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
