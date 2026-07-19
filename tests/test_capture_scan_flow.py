"""ピンチ廃止後のスキャン精度フロー不変条件。"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from capture_scan_flow import (
    CLOSE_RANGE_LIDAR_M,
    CandidateObject,
    CaptureScanFlow,
    GraspObservation,
    ScanMode,
    SizeClass,
    classify_size,
    estimate_weight,
    normalize_scan_capture,
    should_isolate,
)
from spatial_episode import CapturePackage, InteractionRecord


def _small_grasp(**kwargs) -> GraspObservation:
    base = dict(
        hands_used=1,
        contact_fingers=["thumb", "index", "middle"],
        finger_object_distances_m={
            "thumb": 0.01,
            "index": 0.008,
            "middle": 0.012,
        },
        lidar_distance_m=0.40,
        object_extent_m=0.18,
        object_accel_mps2=1.0,
        tip_stiffness_proxy=0.3,
        pinch_gesture=False,
    )
    base.update(kwargs)
    return GraspObservation(**base)


class TestCaptureScanFlow(unittest.TestCase):
    def test_pinch_alone_does_not_switch_mode(self):
        flow = CaptureScanFlow()
        obs = GraspObservation(
            hands_used=1,
            contact_fingers=[],
            finger_object_distances_m={"thumb": 0.05, "index": 0.05},
            pinch_gesture=True,
        )
        flow.on_grasp(obs)
        self.assertEqual(flow.state.mode, ScanMode.ROOM_FULL)

    def test_grasp_contact_enters_candidate_or_close_path(self):
        flow = CaptureScanFlow()
        flow.on_grasp(_small_grasp(), candidates=[
            CandidateObject("book_1", container_id="shelf_living", relation="in"),
        ])
        self.assertIn(flow.state.mode, (ScanMode.OBJECT_CANDIDATE, ScanMode.CLOSE_RANGE))
        self.assertEqual(flow.state.size_class, SizeClass.SMALL)

    def test_two_hands_means_large(self):
        self.assertEqual(
            classify_size(2, object_extent_m=0.2, lidar_distance_m=0.4),
            SizeClass.LARGE,
        )
        flow = CaptureScanFlow()
        flow.on_grasp(GraspObservation(
            hands_used=2,
            contact_fingers=["thumb", "index", "middle", "ring"],
            finger_object_distances_m={
                "thumb": 0.01, "index": 0.01, "middle": 0.01, "ring": 0.01,
            },
            lidar_distance_m=1.2,
            object_extent_m=0.8,
        ), candidates=[CandidateObject("monitor_1")])
        self.assertEqual(flow.state.size_class, SizeClass.LARGE)
        flow.on_gaze("monitor_1", 3.0)
        self.assertEqual(flow.state.mode, ScanMode.LARGE_OBJECT)

    def test_gaze_dwell_starts_close_range_with_isolation(self):
        flow = CaptureScanFlow()
        flow.on_grasp(_small_grasp(), candidates=[
            CandidateObject("book_1", container_id="shelf_living", relation="in"),
        ])
        flow.on_gaze("book_1", 1.0)
        self.assertFalse(flow.state.capturing)
        flow.on_gaze("book_1", 2.5)
        self.assertTrue(flow.state.capturing)
        self.assertEqual(flow.state.mode, ScanMode.CLOSE_RANGE)
        self.assertTrue(flow.state.menu_locked)
        self.assertTrue(should_isolate(flow.state.mode))
        self.assertEqual(flow.assert_precision_invariants(), [])

        meta = flow.build_scan_capture_meta().to_dict()
        self.assertEqual(meta["trigger"], "grasp_contact")
        self.assertTrue(meta["isolationApplied"])
        self.assertEqual(meta["containerID"], "shelf_living")
        self.assertEqual(meta["relation"], "in")
        self.assertLessEqual(meta["profile"]["lidar_focus_m"], CLOSE_RANGE_LIDAR_M)

    def test_menu_unlock_only_via_crown(self):
        flow = CaptureScanFlow()
        flow.on_grasp(_small_grasp(), candidates=[CandidateObject("mug_1")])
        flow.on_gaze("mug_1", 3.0)
        self.assertFalse(flow.finger_menu_allowed())
        flow.on_release()
        self.assertTrue(flow.state.menu_locked)  # still locked after capture
        flow.on_digital_crown()
        self.assertTrue(flow.finger_menu_allowed())

    def test_lidar_near_keeps_small_object_in_close_range(self):
        flow = CaptureScanFlow()
        flow.on_grasp(_small_grasp(lidar_distance_m=1.0), candidates=[
            CandidateObject("book_1"),
        ])
        flow.on_gaze("book_1", 3.0)
        flow.on_lidar_distance(0.35)
        self.assertEqual(flow.state.mode, ScanMode.CLOSE_RANGE)
        self.assertEqual(flow.assert_precision_invariants(), [])

    def test_weight_scales_with_finger_count(self):
        light = estimate_weight(_small_grasp(
            contact_fingers=["thumb", "index"],
            tip_stiffness_proxy=None,
            object_accel_mps2=None,
        ), SizeClass.SMALL)
        heavy = estimate_weight(_small_grasp(
            contact_fingers=["thumb", "index", "middle", "ring"],
            tip_stiffness_proxy=0.8,
            object_accel_mps2=0.3,
        ), SizeClass.SMALL)
        self.assertGreater(heavy.mass_proxy_kg, light.mass_proxy_kg)
        self.assertEqual(heavy.finger_count, 4)

    def test_normalize_and_episode_ingest_scan_capture(self):
        raw = {
            "id": "ir_book_extract",
            "objectID": "book_1",
            "roomID": "kitchen_test",
            "containerID": "shelf_living",
            "actionLabel": "extract",
            "poseHome": {"position": [-0.8, 1.2, -2.0], "rotationYDegrees": 0},
            "poseBefore": {"position": [-0.8, 1.2, -2.0], "rotationYDegrees": 0},
            "poseAfter": {"position": [-0.5, 1.15, -1.7], "rotationYDegrees": 0},
            "motionTrajectory": [],
            "scanCapture": {
                "schemaVersion": 2,
                "mode": "close_range",
                "sizeClass": "small",
                "trigger": "grasp_contact",
                "isolationApplied": True,
                "gazeConfirmed": True,
                "containerID": "shelf_living",
                "relation": "in",
                "weight": {"massProxyKg": 0.31, "fingerCount": 3},
            },
        }
        rec = InteractionRecord.from_dict(raw)
        self.assertIsNotNone(rec.scan_capture)
        self.assertTrue(rec.scan_capture["isolationApplied"])
        from spatial_episode import record_to_episode
        ep = record_to_episode(rec)
        self.assertEqual(ep.meta.get("massProxyKg"), 0.31)
        self.assertTrue(ep.relation_axes["in"])

    def test_sample_room_still_imports(self):
        pkg = CapturePackage(os.path.join(
            ROOT, "benchmarks", "datasets", "sample_room_v1"))
        self.assertGreaterEqual(len(pkg.records), 1)
        book = next(r for r in pkg.records if r.object_id == "book_1")
        self.assertIsNotNone(book.scan_capture)
        self.assertEqual(book.scan_capture.get("trigger"), "grasp_contact")
        self.assertTrue(book.scan_capture.get("isolationApplied"))

    def test_normalize_accepts_snake_case(self):
        n = normalize_scan_capture({
            "mode": "close_range",
            "size_class": "small",
            "isolation_applied": True,
            "gaze_confirmed": True,
            "selected_object_id": "x",
        })
        self.assertTrue(n["isolationApplied"])
        self.assertEqual(n["selectedObjectID"], "x")


if __name__ == "__main__":
    unittest.main()
