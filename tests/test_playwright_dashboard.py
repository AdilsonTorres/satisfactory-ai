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
    mock_save.recipes = []
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

        # Verify flowchart has no syntax errors
        flowchart_content = page.locator("#flowchart-container").text_content()
        assert "Syntax error" not in flowchart_content
        assert "mermaid version" not in flowchart_content

        browser.close()


def test_plan_comparison_cli_vs_web(dashboard_server):
    """Compare the results of generate_late_game_plan with what is shown in the web page results."""
    from tools.late_game_planner import generate_late_game_plan

    # Exact arguments of command:
    # sbot plan-late-game --item 'BWD' --rate 10 --recipe-multiplier 0.75 --sloops BWD
    target_item = "Ballistic Warp Drive"
    target_rate = 10.0
    sloop_items = {"Ballistic Warp Drive"}
    overclock = True
    recipe_multiplier = 0.75

    # Run programmatic plan
    plan = generate_late_game_plan(
        target_item=target_item,
        target_rate=target_rate,
        overclock=overclock,
        sloop_items=sloop_items,
        save_file_path="dummy.sav",
        recipe_multiplier=recipe_multiplier,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Navigate to dashboard planner
        page.goto(dashboard_server)
        page.locator(".tab", has_text="🏭 Factory Planner").click()

        # 2. Fill in the identical inputs
        page.locator("#plan-item").select_option("Ballistic Warp Drive")
        page.locator("#plan-rate").fill("10")
        page.locator("#plan-mode").select_option("late_game")

        # Fill Somersloop input
        page.locator("#plan-sloops").fill("BWD")

        # Set recipe multiplier
        page.locator("#plan-mult").fill("0.75")

        # Set overclocking
        overclock_checkbox = page.locator("#plan-overclock")
        if not overclock_checkbox.is_checked():
            overclock_checkbox.check()

        # 3. Calculate Optimized Plan
        page.locator("button", has_text="Calculate Optimized Plan").click()

        # Wait for results card to be populated
        page.wait_for_selector("#planner-results", state="visible")

        # 4. Scrape calculated values from Web UI
        ui_power_text = page.locator("#plan-total-power").text_content().strip()
        ui_shards_text = page.locator("#plan-total-shards").text_content().strip()
        ui_sloops_text = page.locator("#plan-total-sloops").text_content().strip()

        # 5. Assert total metrics matches
        expected_power = round(plan["total_power_mw"])
        assert f"{expected_power} MW" == ui_power_text
        assert str(plan["total_shards"]) == ui_shards_text
        assert str(plan["total_sloops"]) == ui_sloops_text

        # 6. Assert raw materials match
        ui_raw_rows = page.locator("#plan-raw-table tbody tr")
        ui_raw_materials = {}
        for i in range(ui_raw_rows.count()):
            row = ui_raw_rows.nth(i)
            cells = row.locator("td")
            item_name = cells.nth(0).text_content().strip()
            rate_text = cells.nth(1).text_content().replace("/min", "").strip()
            ui_raw_materials[item_name] = float(rate_text)

        # Check raw materials match within tolerance
        for item, rate in plan["raw_materials"].items():
            assert item in ui_raw_materials
            assert abs(ui_raw_materials[item] - rate) < 0.2

        # 7. Assert steps match
        ui_step_rows = page.locator("#plan-steps-table tbody tr")
        ui_steps = []
        for i in range(ui_step_rows.count()):
            row = ui_step_rows.nth(i)
            cells = row.locator("td")
            item_name = cells.nth(0).text_content().replace("[LOCKED]", "").strip()
            recipe_name = cells.nth(1).text_content().strip()
            rate_text = cells.nth(3).text_content().replace("/min", "").strip()

            ui_steps.append({"item": item_name, "recipe_name": recipe_name, "rate": float(rate_text)})

        assert len(plan["steps"]) == len(ui_steps)
        for expected_step in plan["steps"]:
            matching = [s for s in ui_steps if s["item"] == expected_step["item"]]
            assert len(matching) == 1
            match = matching[0]
            assert match["recipe_name"] == expected_step["recipe_name"]
            assert abs(match["rate"] - expected_step["rate"]) < 0.2

        # Verify flowchart has no syntax errors
        flowchart_content = page.locator("#flowchart-container").text_content()
        assert "Syntax error" not in flowchart_content
        assert "mermaid version" not in flowchart_content

        browser.close()


def test_build_guide_phases_and_mermaid_limit(dashboard_server):
    """Playwright test checking that the build guide phases are rendered and mermaid does not throw text size limit errors."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Open dashboard page and go to Factory Planner
        page.goto(dashboard_server)
        page.locator(".tab", has_text="🏭 Factory Planner").click()

        # 2. Fill in parameters for a large BWD plan to trigger heavy Mermaid rendering
        page.locator("#plan-item").select_option("Ballistic Warp Drive")
        page.locator("#plan-rate").fill("10")
        page.locator("#plan-mode").select_option("late_game")
        page.locator("#plan-sloops").fill("BWD")
        page.locator("#plan-mult").fill("0.75")

        # 3. Calculate Optimized Plan
        page.locator("button", has_text="Calculate Optimized Plan").click()

        # 4. Wait for results card
        page.wait_for_selector("#planner-results", state="visible")

        # 5. Verify Build Guide element exists and displays phase stages
        build_guide_container = page.locator("#plan-build-guide")
        assert build_guide_container.is_visible()
        # Verify it lists phase items (e.g. Phase 1, Phase 2, etc.)
        assert "Phase 1" in build_guide_container.text_content()

        # 6. Verify flowchart rendering did not error out with Maximum text size exceeded or Syntax error
        flowchart_content = page.locator("#flowchart-container").text_content()
        assert "Maximum text size" not in flowchart_content
        assert "exceeded" not in flowchart_content
        assert "Syntax error" not in flowchart_content
        assert "mermaid version" not in flowchart_content

        browser.close()
