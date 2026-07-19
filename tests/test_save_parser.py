import struct
import zlib

from utils.save_parser import (
    SatisfactorySave,
    read_int32,
    read_object_ref,
    read_package_names,
    read_string,
    read_uint8,
    read_version_data,
)


def test_read_uint8():
    data = struct.pack("<B", 255)
    val, offset = read_uint8(data, 0)
    assert val == 255
    assert offset == 1


def test_read_int32():
    data = struct.pack("<i", -42)
    val, offset = read_int32(data, 0)
    assert val == -42
    assert offset == 4


def test_read_string_ascii():
    s = "Hello"
    encoded = s.encode("utf-8") + b"\0"
    data = struct.pack("<i", len(encoded)) + encoded
    val, offset = read_string(data, 0)
    assert val == "Hello"
    assert offset == 4 + len(encoded)


def test_read_string_utf16():
    s = "Hello"
    encoded = s.encode("utf-16-le") + b"\0\0"
    # 6 characters (5 + 1 null terminator) -> length -6
    data = struct.pack("<i", -6) + encoded
    val, offset = read_string(data, 0)
    assert val == "Hello"
    assert offset == 4 + len(encoded)


def test_read_string_empty():
    data = struct.pack("<i", 0)
    val, offset = read_string(data, 0)
    assert val == ""
    assert offset == 4


def test_read_object_ref():
    # object ref consists of levelName and pathName
    data = bytearray()
    # levelName
    l_name = "Persistent_Level"
    l_encoded = l_name.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(l_encoded)) + l_encoded)
    # pathName
    p_name = "Persistent_Level:PersistentLevel.Char_Player_C_0"
    p_encoded = p_name.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(p_encoded)) + p_encoded)

    ref, offset = read_object_ref(bytes(data), 0)
    assert ref["level"] == l_name
    assert ref["path"] == p_name
    assert offset == len(data)


def test_read_package_names():
    # package names helper tests
    data = bytearray()
    data.extend(struct.pack("<I", 1))  # flag1
    name1 = "Name1"
    name1_enc = name1.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(name1_enc)) + name1_enc)

    data.extend(struct.pack("<I", 1))  # flag2
    name2 = "Name2"
    name2_enc = name2.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(name2_enc)) + name2_enc)

    name3 = "Name3"
    name3_enc = name3.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(name3_enc)) + name3_enc)

    names, offset = read_package_names(bytes(data), 0)
    assert names == ["Name1", "Name2", "Name3"]
    assert offset == len(data)


def test_read_version_data():
    data = bytearray()
    data.extend(struct.pack("<I", 123))  # version
    data.extend(struct.pack("<I", 456))  # ue4
    data.extend(struct.pack("<I", 789))  # ue5
    data.extend(struct.pack("<I", 12))  # licensee
    data.extend(struct.pack("<H", 5))  # major
    data.extend(struct.pack("<H", 1))  # minor
    data.extend(struct.pack("<H", 2))  # patch
    data.extend(struct.pack("<I", 333333))  # changelist
    branch = "++UE5+Release-5.1"
    branch_enc = branch.encode("utf-8") + b"\0"
    data.extend(struct.pack("<i", len(branch_enc)) + branch_enc)

    data.extend(struct.pack("<I", 1))  # custom version count
    data.extend(struct.pack("<Q", 1111))  # uuid_a
    data.extend(struct.pack("<Q", 2222))  # uuid_b
    data.extend(struct.pack("<I", 99))  # ver

    res, offset = read_version_data(bytes(data), 0)
    assert res["version"] == 123
    assert res["ue5_version"] == 789
    assert "5.1.2-333333" in res["engine_version"]
    assert res["custom_versions"][0]["version"] == 99
    assert offset == len(data)


def pack_string(s: str) -> bytes:
    if not s:
        return struct.pack("<i", 0)
    encoded = s.encode("utf-8") + b"\0"
    return struct.pack("<i", len(encoded)) + encoded


def make_dummy_save_data(payload_bytes: bytes) -> bytes:
    header = bytearray()
    header.extend(struct.pack("<I", 14))  # header_type
    header.extend(struct.pack("<I", 13))  # save_version
    header.extend(struct.pack("<I", 300000))  # build_version
    header.extend(pack_string("SaveName"))  # save_name
    header.extend(pack_string("Persistent_Level"))  # map_name
    header.extend(
        pack_string(
            "?PlayerInfoSnapshot=0e000000537465616d00040000004e6f6e65000000000000000000000000000000080000004164696c736f6e00"
        )
    )  # map_options with PlatformInfo hex bytes (includes platform "Steam" and username "Adilson")
    header.extend(pack_string("SessionName"))  # session_name
    header.extend(struct.pack("<I", 3600))  # play_duration
    header.extend(struct.pack("<Q", 638000000000000000))  # save_ticks (datetime)
    header.extend(struct.pack("<B", 1))  # session_visibility
    header.extend(struct.pack("<I", 40))  # editor_obj_version
    header.extend(pack_string("ModMetadata"))  # mod_metadata
    header.extend(struct.pack("<I", 0))  # is_modded
    header.extend(pack_string("SaveId"))  # save_id
    header.extend(struct.pack("<I", 1))  # is_partitioned
    header.extend(struct.pack("<I", 1))  # redundant confirm byte
    header.extend(struct.pack("<Q", 12345))  # hash 1
    header.extend(struct.pack("<Q", 67890))  # hash 2
    header.extend(struct.pack("<I", 1))  # is_creative (True)

    chunk = zlib.compress(payload_bytes)

    body = bytearray()
    body.extend(struct.pack("<I", 0x9E2A83C1))  # signature
    body.extend(struct.pack("<I", 0x22222222))
    body.extend(struct.pack("<B", 0))
    body.extend(struct.pack("<I", 131072))  # maxChunkSize
    body.extend(struct.pack("<I", 0x03000000))
    body.extend(struct.pack("<Q", len(chunk)))  # comp_len1
    body.extend(struct.pack("<Q", len(payload_bytes)))  # uncomp_len1
    body.extend(struct.pack("<Q", len(chunk)))  # comp_len2
    body.extend(struct.pack("<Q", len(payload_bytes)))  # uncomp_len2
    body.extend(chunk)

    return bytes(header) + bytes(body)


def make_dummy_payload() -> bytes:
    payload = bytearray()
    payload.extend(struct.pack("<Q", 0))  # _uncomp_size
    payload.extend(struct.pack("<I", 0))  # partition_count
    payload.extend(struct.pack("<I", 0))  # level_count

    # Persistent level
    payload.extend(struct.pack("<Q", 8))  # obj_header_size
    payload.extend(struct.pack("<I", 0))  # actor_count
    payload.extend(struct.pack("<I", 0))  # persistent_flag

    payload.extend(struct.pack("<Q", 4))  # objects_size
    payload.extend(struct.pack("<I", 0))  # obj_count
    payload.extend(struct.pack("<I", 0))  # level_save_ver
    return bytes(payload)


def test_satisfactory_save_parser(tmp_path):
    payload = make_dummy_payload()
    save_bytes = make_dummy_save_data(payload)

    save_file = tmp_path / "test_save.sav"
    save_file.write_bytes(save_bytes)

    # Initialize parser
    save = SatisfactorySave(str(save_file))

    # Verify metadata/header parsed correctly
    assert save.header["save_version"] == 13
    assert save.header["build_version"] == 300000
    assert save.header["save_name"] == "SaveName"
    assert save.header["session_name"] == "SessionName"
    assert save.header["play_duration_seconds"] == 3600
    assert save.header["is_creative"] is True
    assert save.header["is_partitioned"] is True

    # Verify platform ID/username extraction from options
    assert len(save.players) == 0  # no Char_Player actors in mock payload
    assert save.game_phase == "Unknown"
    assert save.hard_drives_unlocked == 0
    assert len(save.dimensional_depot) == 0
    assert len(save.collected_objects) == 0


def test_extract_dimensional_depot():
    objects = {
        "Persistent_Level:PersistentLevel.CentralStorageSubsystem": {
            "type_path": "/Script/FactoryGame.FGCentralStorageSubsystem",
            "properties": {
                "mStoredItems": [
                    {
                        "ItemClass": {
                            "level": "Persistent_Level",
                            "path": "/Game/FactoryGame/Resource/Parts/IronPlate/Desc_IronPlate.Desc_IronPlate_C",
                        },
                        "amount": 42,
                    },
                    {
                        "ItemClass": {
                            "level": "Persistent_Level",
                            "path": "/Game/FactoryGame/Resource/Parts/ReinforcedIronPlate/Desc_ReinforcedIronPlate.Desc_ReinforcedIronPlate_C",
                        },
                        "Amount": 100,
                    },
                ]
            },
        }
    }

    save = object.__new__(SatisfactorySave)
    save.dimensional_depot = []
    save._extract_dimensional_depot(objects)

    assert len(save.dimensional_depot) == 2
    assert save.dimensional_depot[0]["name"] == "Desc_IronPlate"
    assert save.dimensional_depot[0]["quantity"] == 42
    assert save.dimensional_depot[1]["name"] == "Desc_ReinforcedIronPlate"
    assert save.dimensional_depot[1]["quantity"] == 100


def test_extract_game_phase():
    objects = {
        "Persistent_Level:PersistentLevel.GamePhaseManager": {
            "type_path": "/Script/FactoryGame.FGGamePhaseManager",
            "properties": {
                "mCurrentGamePhase": {
                    "level": "Persistent_Level",
                    "path": "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_1.GP_Project_Assembly_Phase_1",
                }
            },
        }
    }
    save = object.__new__(SatisfactorySave)
    save.game_phase = "Unknown"
    save._extract_game_phase(objects)
    assert save.game_phase == "GP_Project_Assembly_Phase_1"


def test_extract_schematics_with_hard_drives():
    objects = {
        "Persistent_Level:PersistentLevel.schematicManager": {
            "type_path": "/Script/FactoryGame.FGSchematicManager",
            "properties": {
                "mPurchasedSchematics": [
                    {
                        "level": "Persistent_Level",
                        "path": "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Screw.Schematic_Alternate_Screw_C",
                    },
                    {
                        "level": "Persistent_Level",
                        "path": "/Game/FactoryGame/Schematics/Progression/Schematic_Tier1_1.Schematic_Tier1_1_C",
                    },
                ]
            },
        }
    }
    save = object.__new__(SatisfactorySave)
    save.schematics = []
    save.metadata = {}
    save._extract_schematics(objects)

    assert "Schematic_Alternate_Screw" in save.schematics
    assert "Schematic_Tier1_1" in save.schematics
    assert save.hard_drives_unlocked == 1


def test_collected_collectibles_summary():
    save = object.__new__(SatisfactorySave)
    save.collected_objects = [
        "Persistent_Level:PersistentLevel.BP_Somersloop_C_0",
        "Persistent_Level:PersistentLevel.BP_MercerSphere_C_1",
        "Persistent_Level:PersistentLevel.BP_Crystal_C_10",  # Blue Slug
        "Persistent_Level:PersistentLevel.BP_Crystal_mk2_C_2",  # Yellow Slug
        "Persistent_Level:PersistentLevel.BP_Crystal_mk3_C_5",  # Purple Slug
    ]
    summary = save.collected_collectibles_summary
    assert summary["somersloop"] == 1
    assert summary["mercer_sphere"] == 1
    assert summary["power_slug_blue"] == 1
    assert summary["power_slug_yellow"] == 1
    assert summary["power_slug_purple"] == 1


def test_extract_recipes():
    objects = {
        "Persistent_Level:PersistentLevel.recipeManager": {
            "type_path": "/Script/FactoryGame.FGRecipeManager",
            "properties": {
                "mAvailableRecipes": [
                    {
                        "level": "Persistent_Level",
                        "path": "/Game/FactoryGame/Recipes/Alternate/Recipe_Alternate_Screw.Recipe_Alternate_Screw_C",
                    },
                    {
                        "level": "Persistent_Level",
                        "path": "/Game/FactoryGame/Recipes/Standard/Recipe_Screw.Recipe_Screw_C",
                    },
                ]
            },
        }
    }
    save = object.__new__(SatisfactorySave)
    save.recipes = []
    save.alternate_recipes_unlocked = 0
    save._extract_recipes(objects)

    assert "Recipe_Alternate_Screw" in save.recipes
    assert "Recipe_Screw" in save.recipes
    assert save.alternate_recipes_unlocked == 1


def test_extract_mam_research():
    objects = {
        "Persistent_Level:PersistentLevel.researchManager": {
            "type_path": "/Script/FactoryGame.FGResearchManager",
            "properties": {
                "mUnlockedResearchTrees": [
                    {
                        "level": "Persistent_Level",
                        "path": "/Game/FactoryGame/Schematics/Research/Research_PowerSlugs.Research_PowerSlugs_C",
                    }
                ]
            },
        }
    }
    save = object.__new__(SatisfactorySave)
    save.unlocked_research_trees = []
    save._extract_mam_research(objects)
    assert "Research_PowerSlugs" in save.unlocked_research_trees


def test_extract_resource_sink():
    objects = {
        "Persistent_Level:PersistentLevel.ResourceSinkSubsystem": {
            "type_path": "/Script/FactoryGame.FGResourceSinkSubsystem",
            "properties": {
                "mTotalPoints": [1000, 2000],
                "mCurrentPointLevels": [5, 10],
                "mNumResourceSinkCoupons": 3,
            },
        }
    }
    save = object.__new__(SatisfactorySave)
    save.resource_sink = {}
    save._extract_resource_sink(objects)

    assert save.resource_sink["total_points_items"] == 1000
    assert save.resource_sink["total_points_dna"] == 2000
    assert save.resource_sink["coupons_earned_items"] == 5
    assert save.resource_sink["coupons_earned_dna"] == 10
    assert save.resource_sink["coupons_available"] == 3


def test_extract_vehicles():
    headers = [
        {"type_path": "/Game/FactoryGame/Buildable/Vehicle/Tractor/BP_Tractor.BP_Tractor_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Vehicle/Tractor/BP_Tractor.BP_Tractor_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Vehicle/Train/Locomotive/BP_Locomotive.BP_Locomotive_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_Golfcart.BP_Golfcart_C"},
    ]
    save = object.__new__(SatisfactorySave)
    save.vehicles = {}
    save._extract_vehicles(headers)

    assert save.vehicles["Tractor"] == 2
    assert save.vehicles["Locomotive"] == 1
    assert save.vehicles["Factory Cart"] == 1


def test_extract_factory_buildings():
    headers = [
        {"type_path": "/Game/FactoryGame/Buildable/Factory/Constructor/Build_Constructor.Build_Constructor_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Factory/Assembler/Build_Assembler.Build_Assembler_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Factory/Miner/Build_MinerMk1.Build_MinerMk1_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Factory/Miner/Build_MinerMk2.Build_MinerMk2_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Factory/Generator/Coal/Build_GeneratorCoal.Build_GeneratorCoal_C"},
        {"type_path": "/Game/FactoryGame/Buildable/Factory/PowerStorage/Build_PowerStorage.Build_PowerStorage_C"},
    ]
    save = object.__new__(SatisfactorySave)
    save.factory_producers = {}
    save.factory_extractors = {}
    save.factory_generators = {}
    save.factory_batteries = 0

    save._extract_factory_buildings(headers, {})

    assert save.factory_producers["Constructor"] == 1
    assert save.factory_producers["Assembler"] == 1
    assert save.factory_extractors["Miner Mk1"] == 1
    assert save.factory_extractors["Miner Mk2"] == 1
    assert save.factory_generators["Coal Generator"] == 1
    assert save.factory_batteries == 1


def test_find_latest_save_file(tmp_path, monkeypatch):
    import os

    from tools.cli import _find_latest_save_file

    def mock_expanduser(path):
        if "~/.local/share" in path:
            return str(tmp_path / "local")
        elif "~/FactoryGame" in path:
            return str(tmp_path / "factory")
        return path

    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)

    assert _find_latest_save_file() is None

    save_dir = (
        tmp_path
        / "local"
        / "Steam"
        / "steamapps"
        / "compatdata"
        / "526870"
        / "pfx"
        / "drive_c"
        / "users"
        / "steamuser"
        / "AppData"
        / "Local"
        / "FactoryGame"
        / "Saved"
        / "SaveGames"
    )
    save_dir.mkdir(parents=True, exist_ok=True)

    assert _find_latest_save_file() is None

    file1 = save_dir / "old_save.sav"
    file2 = save_dir / "new_save.sav"

    file1.write_text("dummy1")
    file2.write_text("dummy2")

    os.utime(file1, (1000, 1000))
    os.utime(file2, (2000, 2000))

    latest = _find_latest_save_file()
    assert latest is not None
    assert os.path.basename(latest) == "new_save.sav"

    # Write a ServerManager save and make it newer
    file3 = save_dir / "ServerManager_V2.sav"
    file3.write_text("dummy3")
    os.utime(file3, (3000, 3000))

    # It should still find new_save.sav because ServerManager files are ignored
    latest = _find_latest_save_file()
    assert latest is not None
    assert os.path.basename(latest) == "new_save.sav"


def test_track_save_progress(tmp_path, monkeypatch):
    import json
    import os

    from tools.cli import _track_save_progress

    original_join = os.path.join
    stats_dir_mock = tmp_path / "stats"
    stats_dir_mock.mkdir(exist_ok=True)

    def mock_join(*args):
        if len(args) >= 2 and args[1] == "save_history.json":
            return str(stats_dir_mock / "save_history.json")
        if len(args) >= 2 and args[-1] == "stats":
            return str(stats_dir_mock)
        return original_join(*args)

    monkeypatch.setattr(os.path, "join", mock_join)

    class DummySave:
        def __init__(self):
            self.filepath = "/path/to/test_save.sav"
            self.header = {
                "session_name": "TestSession",
                "play_duration_seconds": 12345,
                "build_version": 123,
            }
            self.game_phase = "Phase1"
            self.resource_sink = {
                "coupons_earned_items": 10,
                "coupons_earned_dna": 5,
                "coupons_available": 2,
            }
            self.recipes = ["a", "b"]
            self.alternate_recipes_unlocked = 1
            self.hard_drives_unlocked = 2
            self.dimensional_depot = [{"name": "A", "quantity": 1}]
            self.factory_producers = {"Assembler": 5}
            self.factory_extractors = {"Miner": 2}
            self.factory_generators = {"Coal": 3}
            self.factory_batteries = 4

    dummy_save = DummySave()

    _track_save_progress(dummy_save)

    history_file = stats_dir_mock / "save_history.json"
    assert history_file.exists()

    with open(history_file) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["session_name"] == "TestSession"
        assert data[0]["play_duration_seconds"] == 12345
        assert data[0]["producers_count"] == 5

    _track_save_progress(dummy_save)
    with open(history_file) as f:
        data = json.load(f)
        assert len(data) == 1
