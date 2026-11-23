from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from backend.app.models.schemas import EditRequest, SegmentationConfig
from backend.app.services.session_manager import RevisionConflict, SessionManager


class SessionTests(unittest.TestCase):
    def test_exclude_restore_undo_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = SessionManager(Path(temporary))
            nucleus = np.zeros((64, 64), np.uint8); cv2.circle(nucleus, (32, 32), 15, 255, -1)
            protein = np.full((64, 64), 4, np.uint8); protein[nucleus > 0] = 100
            def encode(image):
                return cv2.imencode(".png", image)[1].tobytes()
            state = manager.create_session(encode(nucleus), "nucleus.png", encode(protein), "protein.png", SegmentationConfig(min_nucleus_area=20, protein_channel=0))
            manager.executor.shutdown(wait=True)
            self.assertEqual(state.status, "ready")
            original = manager.result(state.session_id)
            changed = manager.apply_edit(state.session_id, EditRequest(operation="exclude", nucleus_ids=[1], base_revision=0))
            self.assertEqual(changed["aggregate"]["nucleus_count"], 0)
            restored = manager.apply_edit(state.session_id, EditRequest(operation="restore", nucleus_ids=[1], base_revision=1))
            self.assertEqual(restored["aggregate"]["nucleus_count"], 1)
            undone = manager.undo(state.session_id, 2)
            self.assertEqual(undone["aggregate"]["nucleus_count"], 0)
            with self.assertRaises(RevisionConflict):
                manager.apply_edit(state.session_id, EditRequest(operation="restore", nucleus_ids=[1], base_revision=0))
            self.assertEqual(original["aggregate"]["nucleus_count"], 1)


if __name__ == "__main__":
    unittest.main()
