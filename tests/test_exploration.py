from unittest.mock import patch

import numpy as np
import pytest

import activities._shared as shared
from activities.exploration import explore_leg


class MockVision:
    def __init__(self, gauge_frac=0.9, health_low=False, died=False):
        self.gauge_frac = gauge_frac
        self.health_low = health_low
        self.died = died

    def assess(self):
        status = {
            "health_segments": 10 if not self.health_low else 3,
            "health_frac": 1.0 if not self.health_low else 0.3,
            "health_low": self.health_low,
            "damage_red": 0.01,
            "gauge_frac": self.gauge_frac,
            "died": self.died,
        }
        # Return a small mock image region
        return status, np.zeros((10, 10, 3), dtype=np.uint8)


@pytest.fixture(autouse=True)
def mock_temporal_activity():
    with patch("temporalio.activity.heartbeat") as mock_hb, patch("temporalio.activity.info") as mock_info:
        yield mock_hb, mock_info


@pytest.fixture
def mock_input():
    with (
        patch("activities.exploration.inp") as mock_inp,
        patch("activities.exploration.save_debug_screenshot") as mock_screenshot,
    ):
        mock_screenshot.return_value = "/tmp/mock_screenshot.png"
        yield mock_inp, mock_screenshot


def test_explore_leg_normal_flight(mock_input):
    mock_inp, _mock_screenshot = mock_input

    # Flying with good charge (0.90)
    vision = MockVision(gauge_frac=0.90)
    shared._vision = vision

    res = explore_leg(keys=["w"], duration=2.0, check_interval=1.0, gauge_low_abort=0.25)

    assert res["gauge_low"] is False
    assert res["duration"] == 2.0
    assert mock_inp.keys_down.called
    assert mock_inp.keys_up.called


def test_explore_leg_low_charge_abort(mock_input):
    mock_inp, _mock_screenshot = mock_input

    # Flying with low charge (0.15), below threshold (0.25)
    vision = MockVision(gauge_frac=0.15)
    shared._vision = vision

    res = explore_leg(keys=["w"], duration=2.0, check_interval=1.0, gauge_low_abort=0.25)

    assert res["gauge_low"] is True
    # Aborts after the first sleep (chunk 0 checks status, detects low charge, and breaks)
    assert res["duration"] == 1.0
    assert mock_inp.keys_down.called
    assert mock_inp.keys_up.called


def test_explore_leg_grounded_no_abort(mock_input):
    mock_inp, _mock_screenshot = mock_input

    # Grounded (gauge_frac is None)
    vision = MockVision(gauge_frac=None)
    shared._vision = vision

    res = explore_leg(keys=["w"], duration=2.0, check_interval=1.0, gauge_low_abort=0.25)

    assert res["gauge_low"] is False
    assert res["duration"] == 2.0
    assert mock_inp.keys_down.called
    assert mock_inp.keys_up.called
