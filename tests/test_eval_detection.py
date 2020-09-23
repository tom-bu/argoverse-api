# <Copyright 2020, Argo AI, LLC. Released under the MIT license.>
"""Detection evaluation unit tests"""

import logging
import pathlib
from typing import List

import numpy as np
import pytest
from pandas.core.frame import DataFrame
from scipy.spatial.transform import Rotation as R

from argoverse.data_loading.object_label_record import ObjectLabelRecord
from argoverse.evaluation.detection_utils import AffFnType, DistFnType, compute_affinity_matrix, dist_fn, iou_aligned_3d
from argoverse.evaluation.eval_detection import SIGNIFICANT_DIGITS, DetectionCfg, DetectionEvaluator
from argoverse.utils.transform import quat_scipy2argo_vectorized

TEST_DATA_LOC = pathlib.Path(__file__).parent.parent / "tests" / "test_data" / "detection"
logging.getLogger("matplotlib.font_manager").disabled = True


@pytest.fixture
def evaluator() -> DetectionEvaluator:
    """Define an evaluator that compares a set of results to itself."""
    detection_cfg = DetectionCfg(detection_classes=["VEHICLE"])
    return DetectionEvaluator(
        TEST_DATA_LOC / "detections", TEST_DATA_LOC, TEST_DATA_LOC / "test_figures", detection_cfg
    )


@pytest.fixture
def metrics(evaluator: DetectionEvaluator) -> DataFrame:
    return evaluator.evaluate()


def test_affinity_center() -> None:
    """Intialize a detection and a ground truth label. Verify that calculated distance matches expected affinity
    under the specified `AffFnType`.
    """
    dts: List[ObjectLabelRecord] = [ObjectLabelRecord(np.array([0, 0, 0, 0]), np.array([0, 0, 0]), 5.0, 5.0, 5.0, 0)]
    gts: List[ObjectLabelRecord] = [ObjectLabelRecord(np.array([0, 0, 0, 0]), np.array([3, 4, 0]), 5.0, 5.0, 5.0, 0)]

    expected_result: float = -5
    assert compute_affinity_matrix(dts, gts, AffFnType.CENTER) == expected_result


def test_translation_distance() -> None:
    """Intialize a detection and a ground truth label with only translation
    parameters. Verify that calculated distance matches expected distance under
    the specified `DistFnType`.
    """
    dts: DataFrame = DataFrame([{"translation": [0.0, 0.0, 0.0]}])
    gts: DataFrame = DataFrame([{"translation": [5.0, 5.0, 5.0]}])

    expected_result: float = 75.0 ** (1 / 2)
    assert dist_fn(dts, gts, DistFnType.TRANSLATION) == expected_result


def test_scale_distance() -> None:
    """Intialize a detection and a ground truth label with only shape
    parameters (only shape parameters due to alignment assumption).
    Verify that calculated scale error matches the expected value.
    """
    dts: DataFrame = DataFrame([{"width": 5, "height": 5, "length": 5}])
    gts: DataFrame = DataFrame([{"width": 10, "height": 10, "length": 10}])

    expected_result: float = 1 - 0.125
    assert dist_fn(dts, gts, DistFnType.SCALE) == expected_result


def test_orientation_quarter_angles() -> None:
    """Intialize a detection and a ground truth label with only orientation
    parameters. Verify that calculated orientation error matches the expected
    smallest angle ((2 * np.pi) / 4) between the detection and ground truth label.
    """

    # Check all of the 90 degree angles
    expected_result: float = (2 * np.pi) / 4
    quarter_angles = [np.array([0, 0, angle]) for angle in np.arange(0, 2 * np.pi, expected_result)]
    for i in range(len(quarter_angles) - 1):
        dts: DataFrame = DataFrame(
            [{"quaternion": quat_scipy2argo_vectorized(R.from_rotvec(quarter_angles[i]).as_quat())}]
        )
        gts: DataFrame = DataFrame(
            [{"quaternion": quat_scipy2argo_vectorized(R.from_rotvec(quarter_angles[i + 1]).as_quat())}]
        )

        assert np.isclose(dist_fn(dts, gts, DistFnType.ORIENTATION), expected_result)
        assert np.isclose(dist_fn(gts, dts, DistFnType.ORIENTATION), expected_result)


def test_orientation_eigth_angles() -> None:
    """Intialize a detection and a ground truth label with only orientation
    parameters. Verify that calculated orientation error matches the expected
    smallest angle ((2 * np.pi) / 8) between the detection and ground truth label.
    """
    expected_result: float = (2 * np.pi) / 8
    eigth_angle = [np.array([0, 0, angle]) for angle in np.arange(0, 2 * np.pi, expected_result)]
    for i in range(len(eigth_angle) - 1):
        dts: DataFrame = DataFrame(
            [{"quaternion": quat_scipy2argo_vectorized(R.from_rotvec(eigth_angle[i]).as_quat())}]
        )
        gts: DataFrame = DataFrame(
            [{"quaternion": quat_scipy2argo_vectorized(R.from_rotvec(eigth_angle[i + 1]).as_quat())}]
        )

        assert np.isclose(dist_fn(dts, gts, DistFnType.ORIENTATION), expected_result)
        assert np.isclose(dist_fn(gts, dts, DistFnType.ORIENTATION), expected_result)


def test_iou_aligned_3d() -> None:
    """Intialize a detection and a ground truth label with only shape
    parameters (only shape parameters due to alignment assumption).
    Verify that calculated intersection-over-union matches the expected
    value between the detection and ground truth label.
    """
    dt_dims: DataFrame = DataFrame([{"width": 10, "height": 3, "length": 4}])
    gt_dims: DataFrame = DataFrame([{"width": 5, "height": 2, "length": 9}])

    # Intersection is 40 = 4 * 5 * 2 (min of all dimensions).
    # Union is the sum of the two volumes, minus intersection: 270 = (10 * 3 * 4) + (5 * 2 * 9) - 40.
    expected_result: float = 40 / 270.0
    assert iou_aligned_3d(dt_dims, gt_dims) == expected_result


def test_ap(metrics: DataFrame) -> None:
    """Test that AP is 1 for the self-compared results."""
    assert metrics.AP.loc["Average Metrics"] == 1


def test_translation_error(metrics: DataFrame) -> None:
    """Test that ATE is 0 for the self-compared results."""
    assert metrics.ATE.loc["Average Metrics"] == 0


def test_scale_error(metrics: DataFrame) -> None:
    """Test that ASE is 0 for the self-compared results."""
    assert metrics.ASE.loc["Average Metrics"] == 0


def test_orientation_error(metrics: DataFrame) -> None:
    """Test that AOE is 0 for the self-compared results."""
    assert metrics.AOE.loc["Average Metrics"] == 0
