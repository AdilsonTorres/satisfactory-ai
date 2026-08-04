from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from utils.vision import MatchResult, Vision, get_shared, ocr_text


@pytest.fixture
def mock_cfg():
    with patch("utils.vision.cfg.get") as mock_get:
        mock_get.return_value = 0.8
        yield mock_get


@pytest.fixture
def mock_mss():
    with patch("utils.vision.mss.mss") as mock_mss_cls:
        mock_instance = MagicMock()
        mock_mss_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def vision_instance(mock_cfg, mock_mss):
    return Vision()


def test_match_result_str() -> None:
    res = MatchResult(found=True, x=10, y=20, confidence=0.9)
    assert str(res) == "MatchResult(found=True, pos=(10,20), conf=0.900)"
    res2 = MatchResult(found=False, confidence=0.5)
    assert str(res2) == "MatchResult(found=False, best_conf=0.500)"
    assert res.center == (10, 20)


def test_threshold_for(vision_instance, mock_cfg) -> None:
    mock_cfg.return_value = 0.7
    assert vision_instance._threshold_for("test", None) == 0.7
    assert vision_instance._threshold_for("test", 0.9) == 0.9


def test_game_window(vision_instance) -> None:
    with patch("utils.vision.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="12345\n")
        assert vision_instance._game_window() == "12345"
        # Second call should be cached
        assert vision_instance._game_window() == "12345"
        mock_run.assert_called_once()


def test_import_grab(vision_instance) -> None:
    with (
        patch.object(vision_instance, "_game_window", return_value="12345"),
        patch("utils.vision.subprocess.run") as mock_run,
        patch("utils.vision.cv2.imdecode") as mock_decode,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"dummy")
        mock_decode.return_value = np.zeros((10, 10, 3), dtype=np.uint8)

        res = vision_instance._import_grab()
        assert res is not None
        assert res.shape == (10, 10, 3)

        res2 = vision_instance._import_grab((0, 0, 50, 50))
        assert res2 is not None


def test_capture(vision_instance, mock_mss) -> None:
    mock_raw = MagicMock()
    mock_raw.__array__ = MagicMock(return_value=np.zeros((100, 100, 4), dtype=np.uint8))
    mock_mss.grab.return_value = mock_raw

    with patch("utils.vision.cv2.cvtColor", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
        frame = vision_instance.capture()
        assert frame is not None
        assert frame.shape == (100, 100, 3)

    # Test mss fallback
    import mss.exception

    mock_mss.grab.side_effect = mss.exception.ScreenShotError("error")
    with patch.object(vision_instance, "_import_grab", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
        frame2 = vision_instance.capture()
        assert frame2 is not None
        assert vision_instance._mss_broken is True


def test_grab_region(vision_instance) -> None:
    with patch.object(vision_instance, "_import_grab", return_value=np.zeros((50, 50, 3), dtype=np.uint8)):
        region = vision_instance.grab_region(0, 0, 50, 50)
        assert region.shape == (50, 50, 3)

    with (
        patch.object(vision_instance, "_import_grab", return_value=None),
        patch.object(vision_instance, "capture", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
    ):
        region2 = vision_instance.grab_region(0, 0, 10, 10)
        assert region2.shape == (10, 10, 3)


def test_find(vision_instance) -> None:
    with (
        patch.object(vision_instance, "_load_template", return_value=np.zeros((10, 10, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.matchTemplate", return_value=np.zeros((100, 100), dtype=np.float32)),
        patch("utils.vision.cv2.minMaxLoc", return_value=(0.0, 0.9, (0, 0), (5, 5))),
    ):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        res = vision_instance.find("test", frame=frame, threshold=0.8)
        assert res.found is True
        assert res.confidence == 0.9
        assert res.x == 10
        assert res.y == 10

        res2 = vision_instance.find("test", frame=frame, threshold=0.95)
        assert res2.found is False


def test_find_in_region(vision_instance) -> None:
    with (
        patch.object(vision_instance, "grab_region", return_value=np.zeros((50, 50, 3), dtype=np.uint8)),
        patch.object(vision_instance, "_load_template", return_value=np.zeros((10, 10, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.matchTemplate", return_value=np.zeros((50, 50), dtype=np.float32)),
        patch("utils.vision.cv2.minMaxLoc", return_value=(0.0, 0.9, (0, 0), (5, 5))),
    ):
        res = vision_instance.find_in_region("test", (10, 10, 50, 50), threshold=0.8)
        assert res.found is True
        assert res.x == 20
        assert res.y == 20


def test_assess(vision_instance) -> None:
    with (
        patch.object(vision_instance, "grab_region", return_value=np.zeros((200, 760, 3), dtype=np.uint8)),
        patch.object(vision_instance, "_read_gauge_fraction", return_value=0.5),
        patch.object(vision_instance, "_death_overlay_present", return_value=False),
        patch("utils.vision.cv2.cvtColor", return_value=np.zeros((200, 760, 3), dtype=np.uint8)),
    ):
        status, _frame = vision_instance.assess()
        assert status["health_segments"] == 0
        assert status["health_frac"] == 0.0
        assert status["died"] is False
        assert status["gauge_frac"] == 0.5

        status2 = vision_instance.read_player_status()
        assert status2["died"] is False


def test_read_gauge_fraction(vision_instance) -> None:
    with (
        patch.object(vision_instance, "grab_region", return_value=np.zeros((110, 110, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.cvtColor", return_value=np.zeros((110, 110, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.boxFilter", return_value=np.zeros((110, 110, 3), dtype=np.float64)),
    ):
        # With all zeros, conditions for hub and orange won't be met
        assert vision_instance._read_gauge_fraction() is None


def test_death_overlay_present(vision_instance) -> None:
    with (
        patch.object(vision_instance, "_load_template", return_value=np.zeros((10, 10, 3), dtype=np.uint8)),
        patch.object(vision_instance, "grab_region", return_value=np.zeros((130, 470, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.matchTemplate", return_value=np.zeros((130, 470), dtype=np.float32)),
        patch("utils.vision.cv2.minMaxLoc", return_value=(0.0, 0.9, (0, 0), (5, 5))),
    ):
        assert vision_instance._death_overlay_present() is True


def test_load_template(vision_instance) -> None:
    with (
        patch("utils.vision.Path.exists", return_value=True),
        patch("utils.vision.cv2.imread", return_value=np.zeros((10, 10, 3), dtype=np.uint8)),
    ):
        tmpl = vision_instance._load_template("test")
        assert tmpl.shape == (10, 10, 3)
        # Second call uses cache
        tmpl2 = vision_instance._load_template("test")
        assert tmpl2 is tmpl


def test_wait_for(vision_instance) -> None:
    with (
        patch.object(vision_instance, "find") as mock_find,
        patch("utils.vision.time.sleep"),
        patch("utils.vision.time.time", side_effect=[0, 1, 2, 11]),
    ):
        mock_find.return_value = MatchResult(found=False)
        res = vision_instance.wait_for("test", timeout=10.0, poll_interval=1.0)
        assert res.found is False


def test_find_enemy(vision_instance) -> None:
    with (
        patch.object(vision_instance, "grab_region", return_value=np.zeros((720, 1280, 3), dtype=np.uint8)),
        patch.object(
            vision_instance,
            "find",
            return_value=MatchResult(found=True, x=100, y=100, confidence=0.9, template_name="enemy_hog"),
        ),
    ):
        res = vision_instance.find_enemy()
        assert res is not None
        assert res.found is True


def test_scan_all(vision_instance) -> None:
    with (
        patch.object(vision_instance, "capture", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        patch.object(
            vision_instance,
            "find",
            return_value=MatchResult(found=True, x=10, y=10, confidence=0.8, template_name="test"),
        ),
    ):
        res = vision_instance.scan_all(["test"])
        assert "test" in res
        assert res["test"].found is True


def test_read_text_region(vision_instance) -> None:
    with (
        patch.object(vision_instance, "grab_region", return_value=np.zeros((50, 50, 3), dtype=np.uint8)),
        patch("utils.vision.cv2.cvtColor", return_value=np.zeros((50, 50), dtype=np.uint8)),
        patch("utils.vision.cv2.threshold", return_value=(0, np.zeros((50, 50), dtype=np.uint8))),
        patch("utils.vision.pytesseract.image_to_string", return_value="1234"),
    ):
        assert vision_instance.read_text_region(0, 0, 50, 50) == "1234"


def test_ocr_text() -> None:
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    with (
        patch("utils.vision.cv2.cvtColor", return_value=np.zeros((50, 50), dtype=np.uint8)),
        patch("utils.vision.cv2.resize", return_value=np.zeros((100, 100), dtype=np.uint8)),
        patch("utils.vision.cv2.threshold", return_value=(0, np.zeros((100, 100), dtype=np.uint8))),
        patch("utils.vision.pytesseract.image_to_string", return_value="TEXT"),
    ):
        assert ocr_text(img) == "TEXT"


def test_get_shared() -> None:
    s1 = get_shared()
    s2 = get_shared()
    assert s1 is s2
