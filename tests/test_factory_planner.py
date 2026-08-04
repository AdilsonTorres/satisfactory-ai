from unittest.mock import patch

from tools.factory_planner import generate_production_plan, get_coupon_point_cost


def test_get_coupon_point_cost():
    # Test coupon costs for different milestones
    assert get_coupon_point_cost(0) == 1000  # First coupon
    assert get_coupon_point_cost(1) == 1000  # Second
    assert get_coupon_point_cost(2) == 1000  # Third
    assert get_coupon_point_cost(3) == 1500  # Fourth (ceil(4/3)-1 = 1 => 500*1 + 1000 = 1500)
    assert get_coupon_point_cost(10) == 5500  # Eleventh (ceil(11/3)-1 = 3 => 500*9 + 1000 = 5500)


@patch("tools.factory_planner.SatisfactorySave")
def test_generate_production_plan_item(mock_save_class):
    # Setup mock save object
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_PureIronIngot"]
    mock_save.resource_sink = {"coupons_earned_items": 10}

    # Generate a simple plan for 65 Iron Ingots/min
    plan = generate_production_plan(
        target_item="Iron Ingot", target_rate=65.0, coupons_per_minute=None, save_file_path="mock_save.sav"
    )

    assert plan["target_item"] == "Iron Ingot"
    assert plan["target_rate"] == 65.0

    # Pure Iron Ingot needs: 35 Iron Ore + 20 Water per 65 Ingot/min
    assert "Iron Ore" in plan["raw_materials"]
    assert plan["raw_materials"]["Iron Ore"] == 35.0
    assert "Water" in plan["raw_materials"]
    assert plan["raw_materials"]["Water"] == 20.0

    # There should be one step for Iron Ingot (Pure Iron Ingot)
    ingot_steps = [s for s in plan["steps"] if s["item"] == "Iron Ingot"]
    assert len(ingot_steps) == 1
    assert ingot_steps[0]["recipe_name"] == "Pure Iron Ingot"
    assert ingot_steps[0]["unlocked"] is True
    assert ingot_steps[0]["machine_count"] == 1.0  # 65/65


@patch("tools.factory_planner.SatisfactorySave")
def test_generate_production_plan_coupons(mock_save_class):
    mock_save = mock_save_class.return_value
    # Set high coupon count to test points scaling
    mock_save.schematics = []
    mock_save.resource_sink = {"coupons_earned_items": 2176}

    # Generate plan for 0.001 coupons per minute
    # Cost for 2177th coupon: ceil(2177/3) = 726 => 725^2 * 500 + 1000 = 262,813,500 points
    # 0.001 coupons/min = 262,813.5 points/min
    # TPR points = 732,956
    # Rate of TPR = 262813.5 / 732956 = 0.358567 TPR/min
    plan = generate_production_plan(
        target_item=None, target_rate=None, coupons_per_minute=0.001, save_file_path="mock_save.sav"
    )

    assert plan["target_item"] == "Thermal Propulsion Rocket"
    assert abs(plan["target_rate"] - (0.001 * 262813500 / 732956)) < 1e-4


def test_generate_mermaid_flowchart():
    from tools.factory_planner import generate_mermaid_flowchart

    chart = generate_mermaid_flowchart("Iron Ingot", 65.0)
    assert "flowchart TD" in chart
    assert "Iron Ore" in chart
    assert "Smelter" in chart or "Refinery" in chart


@patch("tools.factory_planner.SatisfactorySave")
def test_generate_production_plan_with_recipe_multiplier(mock_save_class):
    mock_save = mock_save_class.return_value
    mock_save.schematics = []

    from tools.factory_planner import generate_production_plan

    # Standard Iron Ingot: 30 Iron Ore -> 30 Iron Ingot (1:1)
    # At 60.0 Iron Ingot/min with recipe_multiplier=0.75:
    # Requires 60.0 * 0.75 = 45.0 Iron Ore
    plan = generate_production_plan(
        target_item="Iron Ingot",
        target_rate=60.0,
        coupons_per_minute=None,
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )
    assert plan["raw_materials"]["Iron Ore"] == 45.0


@patch("tools.factory_planner.SatisfactorySave")
def test_multi_phase_recipe_multiplier_no_exponential_compounding(mock_save_class):
    """Verify recipe_multiplier does not compound exponentially (m^depth) across multi-phase trees."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = []

    from tools.factory_planner import generate_production_plan

    # Modular Frame (depth 0): 2 Reinforced Iron Plate + 12 Iron Rod
    # At target_rate = 10.0 and recipe_multiplier = 0.75:
    # Depth 1 Reinforced Iron Plate rate = 2 * 0.75 * (10 / 2) = 7.5 / min
    # Depth 2 Iron Plate rate for RIP (6 Iron Plate per 2 RIP) = 6 * (7.5 / 2) = 22.5 / min
    # If recipe_multiplier compounded at depth 2, Iron Plate rate would be 6 * 0.75 * (7.5 / 2) = 16.875 (wrong!).
    plan = generate_production_plan(
        target_item="Modular Frame",
        target_rate=10.0,
        coupons_per_minute=None,
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    rip_steps = [s for s in plan["steps"] if s["item"] == "Reinforced Iron Plate"]
    assert len(rip_steps) == 1
    assert abs(rip_steps[0]["rate"] - 11.25) < 1e-4
