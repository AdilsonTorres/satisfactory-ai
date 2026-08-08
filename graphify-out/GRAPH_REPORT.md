# Graph Report - /home/adilson/Projects/github/satisfactory-ai  (2026-08-07)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1091 nodes · 2570 edges · 57 communities (52 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 108 edges (avg confidence: 0.69)
- Token cost: 4,302 input · 544 output

## Graph Freshness
- Built from commit: `b1d73574`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- CLI Entry Point
- Save Parser Tests
- Late Game Planner Tests
- Vision Module Tests
- Exploration Activities
- Combat Activities
- Gameplay Plan Tests
- Doggo Gift Collection
- Factory Planner Tests
- Config Module Tests
- Control & Diagnostics Activities
- Doggo Position Tracking
- Logging & Test Utilities
- Crafting & Navigation Activities
- Workflow Integration Mocks
- Gift Records Persistence
- Depot & Gift Workflow Tests
- Input Module Tests
- Depot Coal Workflow
- CLI Extension Tests
- CLI & Dashboard Tests
- Gift Farm Scheduler
- Fly Calibration Tool
- Game Input Controls
- Project Documentation & Assets
- Dashboard HTTP Handler
- Combat Expedition Workflow
- Calibrate & Travel Tool
- Playwright Dashboard Tests
- Gift Farm Workflow
- Storage & Feeding Activities
- CLI Command Tests
- Input Action Primitives
- Screen Capture & Vision Utils
- Doggo Taming Workflow
- Cursor Movement Utilities
- Combat Patrol Workflow
- Resource Harvest Workflow
- Gift Farm Control CLI
- Workflow Control Mixin
- Mouse Click Utilities
- Capture Labeling Tool
- AFK Session Workflow
- Vision Template Helpers
- Depot Coal Trigger Script
- Gift Farm Trigger Script
- Exploration Trigger Script
- Shift Click Utilities
- Manual Label Application
- Gift Image Classifier
- Game Rules & Config
- Tools CLI Package
- Secrets & Hidden Items
- Save Game Specification
- Project Root Package

## God Nodes (most connected - your core abstractions)
1. `get()` - 50 edges
2. `Vision` - 48 edges
3. `collect_doggo_gift()` - 33 edges
4. `SatisfactorySave` - 33 edges
5. `generate_late_game_plan()` - 29 edges
6. `get_vision()` - 28 edges
7. `screenshot_on_error()` - 24 edges
8. `_ControlMixin` - 24 edges
9. `engage_enemy()` - 23 edges
10. `save_debug_screenshot()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `README - Satisfactory AFK Bot` --references--> `Template Capture Script`  [EXTRACTED]
  README.md → capture_template.py
- `README - Satisfactory AFK Bot` --references--> `Debug Run Script`  [EXTRACTED]
  README.md → debug_run.py
- `README - Satisfactory AFK Bot` --references--> `Label Captures Script`  [EXTRACTED]
  README.md → label_captures.py
- `README - Satisfactory AFK Bot` --references--> `Passive Screen Capture Script`  [EXTRACTED]
  README.md → passive_capture.py
- `_screenshot()` --indirect_call--> `take_debug_screenshot()`  [INFERRED]
  workflows/_base.py → activities/diagnostics.py

## Import Cycles
- None detected.

## Communities (57 total, 5 thin omitted)

### Community 0 - "CLI Entry Point"
Cohesion: 0.07
Nodes (63): ArgumentParser, main(), create_parser(), _find_latest_save_file(), _get_acronym_mapping(), main(), Any, Namespace (+55 more)

### Community 1 - "Save Parser Tests"
Cohesion: 0.08
Nodes (36): make_dummy_payload(), make_dummy_save_data(), pack_string(), Any, test_find_latest_save_file(), test_read_int32(), test_read_object_ref(), test_read_package_names() (+28 more)

### Community 2 - "Late Game Planner Tests"
Cohesion: 0.06
Nodes (62): Any, patch, A close typo should raise ValueError with suggestions., A completely unrelated string should raise ValueError without suggestions., The label parameter should appear in the error message., generate_late_game_plan should reject a typo before parsing the save., generate_late_game_plan should validate sloop item names too., Exact match should return immediately without prompting. (+54 more)

### Community 3 - "Vision Module Tests"
Cohesion: 0.05
Nodes (25): mock_cfg(), mock_mss(), fixture, test_find_enemy(), test_get_shared(), test_match_result_str(), test_ocr_text(), test_scan_all() (+17 more)

### Community 4 - "Exploration Activities"
Cohesion: 0.07
Nodes (36): capture_base_reference(), explore_leg(), get_exploration_route(), Any, defn, activities/exploration.py Exploration activities., Reads [exploration] from config.toml — config/file I/O must happen in an…, Snapshots the character's current position as the 'base' reference point for an… (+28 more)

### Community 5 - "Combat Activities"
Cohesion: 0.09
Nodes (39): check_ammo_count(), engage_enemy(), Any, defn, activities/combat.py Combat-related activities., Retreats without engaging — used when scan_for_enemy signals 'hazard' (a…, Reads the ammo count from the HUD via OCR (region configurable in config.toml…, Engages an enemy at (target_x, target_y) using tactical movement strategies.… (+31 more)

### Community 6 - "Gameplay Plan Tests"
Cohesion: 0.12
Nodes (37): test_get_recipe_recommendations_all_missing(), test_get_recipe_recommendations_some_unlocked(), _base_save(), Any, test_build_factory_snapshot(), test_build_gameplay_plan_aggregates(), test_build_milestone_summary(), test_build_progress_delta_no_history() (+29 more)

### Community 7 - "Doggo Gift Collection"
Cohesion: 0.11
Nodes (38): _any_doggo_name_matches(), _camera_responds(), collect_doggo_gift(), _doggo_name_matches(), _empty_ref_key(), _empty_slot_reference(), _face_doggo_and_recheck(), _gift_prompt_region() (+30 more)

### Community 8 - "Factory Planner Tests"
Cohesion: 0.08
Nodes (36): Any, patch, Verify recipe_multiplier does not compound exponentially (m^depth) across…, test_generate_mermaid_flowchart(), test_generate_production_plan_coupons(), test_generate_production_plan_item(), test_generate_production_plan_with_recipe_multiplier(), test_get_coupon_point_cost() (+28 more)

### Community 9 - "Config Module Tests"
Cohesion: 0.09
Nodes (35): Any, test_config_get_default(), test_config_get_existing(), test_config_get_nested(), test_config_load(), test_config_missing_file(), test_config_reload(), AppConfig (+27 more)

### Community 10 - "Control & Diagnostics Activities"
Cohesion: 0.09
Nodes (30): defn, activities/control.py Control-plane activities: signal an EXISTING workflow…, Connects a fresh Temporal client and sends `signal_name` to…, send_workflow_signal(), capture_template_screen(), extract_templates_from_screen(), persist_session_stats(), Any (+22 more)

### Community 11 - "Doggo Position Tracking"
Cohesion: 0.10
Nodes (34): _clear_miss_count(), _load_doggo_position(), Any, Load a doggo's learned camera position (yaw + pitch offsets from home). Returns…, Persist a doggo's camera position (yaw + pitch from home)., Drop a doggo's learned position so the next cycle re-discovers it., Tracks consecutive 'no gift prompt visible' misses for ANY doggo. After…, _record_miss_or_reset() (+26 more)

### Community 12 - "Logging & Test Utilities"
Cohesion: 0.09
Nodes (27): AbstractEventLoop, Client, Any, test_exceptions(), test_logger_setup(), test_stats_save(), test_is_fail_safe_key(), utils/logger.py Logging to console + rotating file at logs/bot.log. (+19 more)

### Community 13 - "Crafting & Navigation Activities"
Cohesion: 0.11
Nodes (25): craft_rifle_ammo(), harvest_resource_node(), defn, activities/crafting.py Crafting and harvesting activities., Harvests a resource node (manual pickaxe or a node already opened up by a…, navigate_back_to_base(), navigate_to_equipment_workshop(), defn (+17 more)

### Community 14 - "Workflow Integration Mocks"
Cohesion: 0.21
Nodes (26): mock_capture_template_screen(), mock_check_ammo_count(), mock_deposit_coal_to_storage(), mock_download_coal_from_depot(), mock_engage_enemy(), mock_extract_templates_from_screen(), mock_feed_wild_doggo(), mock_handle_death_respawn() (+18 more)

### Community 15 - "Gift Records Persistence"
Cohesion: 0.13
Nodes (22): Any, defn, activities/records.py Persistence activities. These do NOT touch the game or…, Persist one doggo gift check (collected or empty) to stats/gift_history.db.…, record_gift_check(), Connection, Any, Tests for utils/gift_db.py (per-doggo gift history). (+14 more)

### Community 16 - "Depot & Gift Workflow Tests"
Cohesion: 0.14
Nodes (22): mock_check_inventory_full(), mock_collect_doggo_gift(), mock_craft_rifle_ammo(), mock_deposit_coal_to_storage(), mock_download_coal_from_depot(), mock_navigate_back_to_base(), mock_navigate_to_equipment_workshop(), mock_persist_session_stats() (+14 more)

### Community 17 - "Input Module Tests"
Cohesion: 0.12
Nodes (19): mock_cfg(), mock_mouse(), mock_sleep(), mock_uinput(), fixture, test_active_window_name(), test_aim_at_screen_position(), test_focus_game() (+11 more)

### Community 18 - "Depot Coal Workflow"
Cohesion: 0.13
Nodes (14): query, _cleanup_on_cancel(), Any, Closes any open menus in the game before letting the cancellation exception…, _save_stats(), DepotCoalParams, DepotCoalToStorageWorkflow, Any (+6 more)

### Community 19 - "CLI Extension Tests"
Cohesion: 0.12
Nodes (16): Verify that --draw and --draw-html flags are parsed correctly for factory plans., Verify that --draw-html option is parsed correctly for the map subcommand., Verify that dashboard subcommand is parsed correctly with --port option., Verify that DashboardHandler internal methods run without error and return…, Verify watcher globals are present and initialized., Verify that update_config_value correctly updates properties inside config.toml., Verify 3D distance calculations in map_power., Verify that dashboard module contains start_server and handler. (+8 more)

### Community 20 - "CLI & Dashboard Tests"
Cohesion: 0.12
Nodes (17): patch, Verify that _save_map_html correctly writes the map file., Verify that _trigger_workflow_async and _run_schedule_action_async map…, Verify that sbot start executes the boot sequence for compose, worker, and…, Verify that _get_temporal_audit_log safely returns items when Temporal handles…, Verify that _get_map_html generates the file and the planner handles acronyms., Verify that _save_flowchart_html correctly generates and saves an HTML…, Verify that Somersloop items are successfully resolved to full names before… (+9 more)

### Community 21 - "Gift Farm Scheduler"
Cohesion: 0.33
Nodes (15): _client(), create(), delete(), _discover_schedule_ids(), _hhmm_to_calendar(), main(), pause(), Namespace (+7 more)

### Community 22 - "Fly Calibration Tool"
Cohesion: 0.24
Nodes (14): test_keys_down_up(), test_resolve_key_code(), _diff(), full_frame(), main(), Any, fly_calibrate.py (one-off, scratch) Flies the character with the Hover Pack to…, _win() (+6 more)

### Community 23 - "Game Input Controls"
Cohesion: 0.18
Nodes (14): download_coal_from_depot(), Open player inventory, search for 'coal' in the Dimensional Depot panel, and…, test_ensure_game_input_ready(), test_press(), test_respawn_confirm(), close_menu(), ensure_game_input_ready(), _get_mouse() (+6 more)

### Community 24 - "Project Documentation & Assets"
Cohesion: 0.15
Nodes (14): Template Capture Script, Temporal Workflow Orchestration, uinput Virtual Mouse Input, Computer Vision Template Matching, Vision.assess() Health Bar Reader, Debug Run Script, Docker Compose Configuration, Deploy Worker Topology (+6 more)

### Community 25 - "Dashboard HTTP Handler"
Cohesion: 0.32
Nodes (4): DashboardHandler, Any, Updates config.toml value keeping existing comments and spacing formatting., update_config_value()

### Community 26 - "Combat Expedition Workflow"
Cohesion: 0.16
Nodes (10): CombatExpeditionWorkflow, defn, Full combat expedition: 1. Checks ammo at the base — crafts more before…, BaseModel, defn, run, workflows/control.py Tiny one-shot workflow used as the ACTION for Temporal…, SignalWorkflowAction (+2 more)

### Community 27 - "Calibrate & Travel Tool"
Cohesion: 0.24
Nodes (12): Retraces legs_taken in reverse order with mirrored keys (w<->s, a<->d; 'space'…, return_via_reverse_route(), test_opposite_keys(), calibrate_and_travel(), get_player_state(), Any, tools/calibrate_and_travel.py Automatically calibrates camera turn sensitivity…, trigger_quicksave() (+4 more)

### Community 28 - "Playwright Dashboard Tests"
Cohesion: 0.22
Nodes (12): dashboard_server(), get_free_port(), Any, fixture, Compare the results of generate_late_game_plan with what is shown in the web…, Playwright test checking that the build guide phases are rendered and mermaid…, Playwright test checking that the dashboard UI accurately renders 100.0% for…, Verify that all pages are working, and perform late game calculation flow. (+4 more)

### Community 29 - "Gift Farm Workflow"
Cohesion: 0.21
Nodes (9): DoggoParam, GiftFarmParams, GiftFarmWorkflow, Any, BaseModel, defn, run, workflows/gift_farm.py AFK Gift Farm workflow — multi-doggo. (+1 more)

### Community 30 - "Storage & Feeding Activities"
Cohesion: 0.17
Nodes (11): deposit_coal_to_storage(), feed_wild_doggo(), open_storage_and_deposit_loot(), defn, Opens a storage container (needs the interaction prompt in range) and sweeps…, Attempts to tame a wild Lizard Doggo: opens the inventory, drags a Paleberry to…, Open the storage container in front of the player, locate all Coal stacks in…, CombatExpeditionParams (+3 more)

### Community 31 - "CLI Command Tests"
Cohesion: 0.20
Nodes (12): Any, asyncio, Test trigger_calibration script execution., Verify that _run_dashboard invokes tools.dashboard.start_server., Test that sbot plan-late-game output prints the disposal items (like Petroleum…, Test that _run_status behaves correctly if Temporal is unreachable., Test that schedules list routes properly to schedule_gift_farm.status., test_cli_plan_late_game_bwd_disposal() (+4 more)

### Community 32 - "Input Action Primitives"
Cohesion: 0.33
Nodes (11): test_actions(), test_hold(), dodge(), hold(), interact(), loot_remains(), move_backward(), move_forward() (+3 more)

### Community 33 - "Screen Capture & Vision Utils"
Cohesion: 0.18
Nodes (9): capture_fullscreen(), ndarray, capture_template.py Helper script for capturing game templates. Runs outside…, Captures the screen and lets the user select a region with the mouse., select_roi_and_save(), main(), Any, gauge_record.py (one-off, scratch) Passive (read-only) recorder: samples the… (+1 more)

### Community 34 - "Doggo Taming Workflow"
Cohesion: 0.20
Nodes (9): _screenshot(), Any, BaseModel, defn, run, workflows/tame_doggo.py Lizard Doggo taming workflow., Tries to tame a wild Lizard Doggo by repeatedly offering Paleberries (multiple…, TameDoggoParams (+1 more)

### Community 35 - "Cursor Movement Utilities"
Cohesion: 0.20
Nodes (11): test_drag(), test_home_cursor(), test_move_cursor_to(), test_step_move(), drag(), _home_cursor(), move_cursor_to(), Park the in-game UI cursor at the top-left corner (0, 0). The game holds an… (+3 more)

### Community 36 - "Combat Patrol Workflow"
Cohesion: 0.20
Nodes (8): CombatPatrolParams, CombatPatrolWorkflow, Any, BaseModel, defn, run, workflows/combat_patrol.py Combat Patrol workflow., Static patrol: stays in place and reacts to enemies entering the field of view.…

### Community 37 - "Resource Harvest Workflow"
Cohesion: 0.20
Nodes (8): Any, BaseModel, defn, run, workflows/resource_harvest.py Manual Resource Harvesting workflow., Manual harvesting loop at a fixed resource node. The player needs to be…, ResourceHarvestParams, ResourceHarvestWorkflow

### Community 38 - "Gift Farm Control CLI"
Cohesion: 0.51
Nodes (9): _client(), main(), pause(), Namespace, gift_farm_ctl.py Convenience control for GiftFarmWorkflow: start / stop / pause…, resume(), start(), status() (+1 more)

### Community 39 - "Workflow Control Mixin"
Cohesion: 0.32
Nodes (3): signal, _ControlMixin, Signals and query shared by all workflows.

### Community 40 - "Mouse Click Utilities"
Cohesion: 0.25
Nodes (8): test_click(), test_right_click(), test_shoot(), click(), _get_uinput_mouse(), Virtual mouse device via uinput — handles relative movement and button clicks., right_click(), shoot()

### Community 41 - "Capture Labeling Tool"
Cohesion: 0.46
Nodes (7): _crop_and_save(), main(), Any, Path, label_captures.py Manual classification tool: walks through the screenshots…, run(), _show_resizable()

### Community 42 - "AFK Session Workflow"
Cohesion: 0.29
Nodes (5): AfkSessionWorkflow, Any, defn, run, Alternating rotations of gift farming + combat patrol. Parameters: gift_cycles…

### Community 43 - "Vision Template Helpers"
Cohesion: 0.33
Nodes (6): _finder(), press_until_open(), Fixed screen region configured for `template` under [vision.regions.<name>] in…, A zero-arg callable that looks for `template`. Uses the fast cropped path when…, Recapture the game's mouse focus and press `key_action`, retrying until…, _region_for()

### Community 44 - "Depot Coal Trigger Script"
Cohesion: 0.40
Nodes (4): Test trigger_depot_coal script execution., test_trigger_depot_coal(), main(), Any

### Community 45 - "Gift Farm Trigger Script"
Cohesion: 0.40
Nodes (4): Test trigger_gift_farm script execution., test_trigger_gift_farm(), main(), Any

### Community 46 - "Exploration Trigger Script"
Cohesion: 0.40
Nodes (4): Test trigger_exploration script execution., test_trigger_exploration(), main(), Any

### Community 47 - "Shift Click Utilities"
Cohesion: 0.40
Nodes (5): test_shift_click(), test_shift_click_here(), Shift+left-click at the CURRENT cursor position (no cursor walk). Used when the…, shift_click(), shift_click_here()

### Community 48 - "Manual Label Application"
Cohesion: 0.50
Nodes (3): apply_labels(), Any, tools/apply_manual_labels.py Applies the visual item identifications to the…

### Community 49 - "Gift Image Classifier"
Cohesion: 0.50
Nodes (3): classify_gifts(), Any, tools/classify_gifts.py Uses image clustering to identify Lizard Doggo gifts…

## Knowledge Gaps
- **12 isolated node(s):** `satisfactory-ai`, `Gemini Agent Project Configuration`, `Docker Compose Configuration`, `Satisfactory Game Design & Factory Layout Guides`, `Save Game Parser Specification` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Doggo Gift Collection` to `CLI Entry Point`, `Input Action Primitives`, `Cursor Movement Utilities`, `Exploration Activities`, `Combat Activities`, `Gift Farm Control CLI`, `Mouse Click Utilities`, `Config Module Tests`, `Vision Template Helpers`, `Depot Coal Trigger Script`, `Crafting & Navigation Activities`, `Gift Farm Trigger Script`, `Logging & Test Utilities`, `Gift Farm Scheduler`, `Game Input Controls`, `Storage & Feeding Activities`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `SatisfactorySave` connect `Save Parser Tests` to `CLI Entry Point`, `Late Game Planner Tests`, `Gameplay Plan Tests`, `Factory Planner Tests`, `Calibrate & Travel Tool`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `Vision` connect `Doggo Gift Collection` to `CLI Entry Point`, `Screen Capture & Vision Utils`, `Vision Module Tests`, `Combat Activities`, `Vision Template Helpers`, `Fly Calibration Tool`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `collect_doggo_gift()` (e.g. with `activities/__init__.py` and `._run_session()`) actually correct?**
  _`collect_doggo_gift()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `satisfactory-ai`, `Gemini Agent Project Configuration`, `Docker Compose Configuration` to the rest of the system?**
  _12 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI Entry Point` be split into smaller, more focused modules?**
  _Cohesion score 0.06804214223002635 - nodes in this community are weakly interconnected._
- **Should `Save Parser Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.08028846153846154 - nodes in this community are weakly interconnected._