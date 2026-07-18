import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import sync_playwright


def get_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture(scope="module")
def dashboard_server():
    from tools.dashboard import start_server

    port = get_free_port()

    # Create a mock save instance that has some standard unlocked items
    mock_save = MagicMock()
    mock_save.schematics = [
        "Schematic_Alternate_PureIronIngot",
        "Schematic_Alternate_SuperpositionOscillator",
    ]
    mock_save.resource_sink = {"coupons_earned_items": 10}
    mock_save.dimensional_depot = []

    # Mock browser opening and latest save file checking
    with (
        patch("webbrowser.open"),
        patch("tools.cli._find_latest_save_file") as mock_find_save,
        patch("tools.late_game_planner.SatisfactorySave") as mock_save_lg,
        patch("tools.factory_planner.SatisfactorySave") as mock_save_std,
    ):
        mock_find_save.return_value = "dummy.sav"
        mock_save_lg.return_value = mock_save
        mock_save_std.return_value = mock_save

        # Start server in background thread
        t = threading.Thread(target=lambda: start_server(port=port), daemon=True)
        t.start()

        # Wait for server to start up
        time.sleep(1.0)
        yield f"http://localhost:{port}"


def test_dashboard_factory_planner_flow(dashboard_server):
    """Verify that all pages are working, and perform late game calculation flow."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Open dashboard page
        page.goto(dashboard_server)

        # 2. Wait for page load and check title
        assert page.title() == "Satisfactory gameplay Dashboard"

        # 3. Verify all tabs exist and can be switched to
        tabs = [
            ("📊 Telemetry & Stats", "#telemetry"),
            ("🖼️ Screenshot Gallery", "#gallery"),
            ("🗺️ Live Power Grid Map", "#map-view"),
            ("🎮 Active Controls", "#controls"),
            ("🎛️ Calibration Wizard", "#calibration"),
            ("🏭 Factory Planner", "#planner-view"),
        ]
        for label, selector in tabs:
            tab_button = page.locator(".tab", has_text=label)
            assert tab_button.is_visible()
            tab_button.click()
            # Verify active content class
            assert "active" in page.eval_on_selector(selector, "el => el.className")

        # Switch back to Factory Planner
        page.locator(".tab", has_text="🏭 Factory Planner").click()

        # 4. Fill in planning options:
        # Select Ballistic Warp Drive
        page.locator("#plan-item").select_option("Ballistic Warp Drive")

        # Select Late-Game Specialized Scaling
        page.locator("#plan-mode").select_option("late_game")

        # Enter BWD in somersloop input
        sloops_input = page.locator("#plan-sloops")
        sloops_input.fill("BWD")

        # Click calculate optimized plan button
        calculate_btn = page.locator("button", has_text="Calculate Optimized Plan")
        calculate_btn.click()

        # Wait for results card/table to become visible
        page.wait_for_selector("#planner-results", state="visible")

        # 5. Validate the calculated results:
        # Verify raw materials table contains items
        assert page.locator("#plan-raw-table tbody tr").first.is_visible()

        # Verify steps table contains resolved target item "Ballistic Warp Drive"
        assert "Ballistic Warp Drive" in page.locator("#plan-steps-table tbody").text_content()

        # Verify Somersloops requirements metrics are visible
        assert page.locator("#plan-total-sloops").text_content() != "0"

        browser.close()
