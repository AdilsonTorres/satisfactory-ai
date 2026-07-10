from utils.alternate_advisor import get_recipe_recommendations


def test_get_recipe_recommendations_all_missing():
    res = get_recipe_recommendations([])
    assert res["total_ranked_unlocked"] == 0
    assert len(res["unlocked"]["S"]) == 0
    assert len(res["unlocked"]["A"]) == 0
    assert len(res["unlocked"]["B"]) == 0
    assert len(res["unlocked"]["C"]) == 0
    assert len(res["unlocked"]["D"]) == 0
    assert len(res["unlocked"]["F"]) == 0

    assert len(res["missing"]["S"]) > 0
    assert len(res["missing"]["A"]) > 0
    assert len(res["missing"]["B"]) > 0
    assert len(res["missing"]["C"]) > 0
    assert len(res["missing"]["D"]) > 0
    assert len(res["missing"]["F"]) > 0

    assert any("Target hard drives to unlock missing S-Tier" in a for a in res["advice"])


def test_get_recipe_recommendations_some_unlocked():
    # Unlock Diluted Fuel (S), Steel Screw (A), Cast Screw (F), Recycled Rubber (A), and Stitched Iron Plate (B)
    unlocked = [
        "Schematic_Alternate_DilutedFuel",  # Diluted Fuel
        "Schematic_Alternate_Screw2",  # Steel Screw
        "Schematic_Alternate_Screw",  # Cast Screw
        "Schematic_Alternate_RecycledRubber",  # Recycled Rubber
        "Schematic_Alternate_ReinforcedIronPlate1",  # Stitched Iron Plate (B)
    ]

    res = get_recipe_recommendations(unlocked)

    # Diluted Fuel + Steel Screw + Recycled Rubber + Stitched Iron Plate are S/A/B
    assert res["total_ranked_unlocked"] == 4

    # Verify lists
    s_names = [r["name"] for r in res["unlocked"]["S"]]
    assert "Diluted Fuel" in s_names

    a_names = [r["name"] for r in res["unlocked"]["A"]]
    assert "Recycled Rubber" in a_names
    assert "Steel Screw" in a_names

    b_names = [r["name"] for r in res["unlocked"]["B"]]
    assert "Stitched Iron Plate" in b_names

    f_names = [r["name"] for r in res["unlocked"]["F"]]
    assert "Cast Screw" in f_names

    # Advice should warn about Cast Screw but recommend steel screw migration
    assert any("migrated to Steel Screws" in a for a in res["advice"])
