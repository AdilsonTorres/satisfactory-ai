import datetime
import struct
import zlib
from typing import Any

from pydantic import BaseModel


class DimensionalDepotItem(BaseModel):
    item_id: str
    name: str
    quantity: int

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


# Constants
TICKS_IN_SECOND = 10 * 1000 * 1000
EPOCH_1_TO_1970 = 719162 * 24 * 60 * 60
DEBUG_PARSER = False


class ParseError(Exception):
    pass


# Helper functions for binary reading
def read_bytes(data: bytes, offset: int, length: int) -> tuple[bytes, int]:
    if offset + length > len(data):
        raise ParseError(f"Offset {offset} + length {length} out of bounds for data size {len(data)}")
    return data[offset : offset + length], offset + length


def read_uint8(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 1)
    return struct.unpack("<B", val)[0], offset


def read_int8(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 1)
    return struct.unpack("<b", val)[0], offset


def read_uint16(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 2)
    return struct.unpack("<H", val)[0], offset


def read_int32(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 4)
    return struct.unpack("<i", val)[0], offset


def read_uint32(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 4)
    return struct.unpack("<I", val)[0], offset


def read_int64(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 8)
    return struct.unpack("<q", val)[0], offset


def read_uint64(data: bytes, offset: int) -> tuple[int, int]:
    val, offset = read_bytes(data, offset, 8)
    return struct.unpack("<Q", val)[0], offset


def read_float(data: bytes, offset: int) -> tuple[float, int]:
    val, offset = read_bytes(data, offset, 4)
    return struct.unpack("<f", val)[0], offset


def read_double(data: bytes, offset: int) -> tuple[float, int]:
    val, offset = read_bytes(data, offset, 8)
    return struct.unpack("<d", val)[0], offset


def read_string(data: bytes, offset: int) -> tuple[str, int]:
    strlen, offset = read_int32(data, offset)
    if strlen == 0:
        return "", offset

    if strlen > 0:
        val, offset = read_bytes(data, offset, strlen)
        return val[:-1].decode("utf-8", errors="replace"), offset
    else:
        # UTF-16 string (negative length)
        byte_len = -strlen * 2
        val, offset = read_bytes(data, offset, byte_len)
        return val[:-2].decode("utf-16", errors="replace"), offset


def read_object_ref(data: bytes, offset: int) -> tuple[dict[str, str], int]:
    level_name, offset = read_string(data, offset)
    path_name, offset = read_string(data, offset)
    return {"level": level_name, "path": path_name}, offset


def read_package_names(data: bytes, offset: int) -> tuple[list[str], int]:
    package_names = []
    flag1, offset = read_uint32(data, offset)
    if flag1 != 0:
        name1, offset = read_string(data, offset)
        package_names.append(name1)
        flag2, offset = read_uint32(data, offset)
        if flag2 != 0:
            name2, offset = read_string(data, offset)
            name3, offset = read_string(data, offset)
            package_names.extend([name2, name3])
    return package_names, offset


def read_version_data(data: bytes, offset: int) -> tuple[dict[str, Any], int]:
    version, offset = read_uint32(data, offset)
    ue4_ver, offset = read_uint32(data, offset)
    ue5_ver, offset = read_uint32(data, offset)
    licensee_ver, offset = read_uint32(data, offset)

    major, offset = read_uint16(data, offset)
    minor, offset = read_uint16(data, offset)
    patch, offset = read_uint16(data, offset)
    changelist, offset = read_uint32(data, offset)
    branch, offset = read_string(data, offset)

    custom_count, offset = read_uint32(data, offset)
    custom_versions = []
    for _ in range(custom_count):
        uuid_a, offset = read_uint64(data, offset)
        uuid_b, offset = read_uint64(data, offset)
        ver, offset = read_uint32(data, offset)
        custom_versions.append({"uuid": (uuid_a, uuid_b), "version": ver})

    return {
        "version": version,
        "ue4_version": ue4_ver,
        "ue5_version": ue5_ver,
        "licensee_version": licensee_ver,
        "engine_version": f"{major}.{minor}.{patch}-{changelist} ({branch})",
        "custom_versions": custom_versions,
    }, offset


class SatisfactorySave:
    """
    A lightweight, clean parser for Satisfactory save games (.sav) that only reads
    the essential data (metadata, players, inventory items, achievements)
    without executing any unsafe code.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.header: dict[str, Any] = {}
        self.players: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {}
        self.schematics: list[str] = []
        self._decompressed_data: bytes = b""
        self.collected_objects: list[str] = []
        self.dimensional_depot: list[DimensionalDepotItem] = []
        self.game_phase: str = "Unknown"
        self.hard_drives_unlocked: int = 0
        self.recipes: list[str] = []
        self.alternate_recipes_unlocked: int = 0
        self.unlocked_research_trees: list[str] = []
        self.resource_sink: dict[str, int] = {}
        self.vehicles: dict[str, int] = {}
        self.factory_producers: dict[str, int] = {}
        self.factory_extractors: dict[str, int] = {}
        self.factory_generators: dict[str, int] = {}
        self.factory_batteries: int = 0

        self._load_and_parse()

    def _load_and_parse(self):
        with open(self.filepath, "rb") as f:
            raw_data = f.read()

        offset = self._parse_header(raw_data)
        self._decompressed_data = self._decompress_body(raw_data, offset)
        self._parse_payload()

    def _parse_header(self, data: bytes) -> int:
        offset = 0
        header_type, offset = read_uint32(data, offset)
        if header_type != 13 and header_type != 14:
            raise ParseError(f"Unsupported header type {header_type}")

        save_version, offset = read_uint32(data, offset)
        build_version, offset = read_uint32(data, offset)

        save_name = ""
        if header_type >= 14:
            save_name, offset = read_string(data, offset)

        map_name, offset = read_string(data, offset)
        map_options, offset = read_string(data, offset)
        session_name, offset = read_string(data, offset)
        play_duration, offset = read_uint32(data, offset)
        save_ticks, offset = read_uint64(data, offset)

        try:
            save_datetime = datetime.datetime.fromtimestamp(save_ticks / TICKS_IN_SECOND - EPOCH_1_TO_1970)
        except Exception:
            save_datetime = datetime.datetime.min

        session_visibility, offset = read_uint8(data, offset)

        if save_version >= 7:
            _editor_obj_version, offset = read_uint32(data, offset)

        if save_version >= 8:
            _mod_metadata, offset = read_string(data, offset)

        is_modded, offset = read_uint32(data, offset)

        if save_version >= 10:
            _save_id, offset = read_string(data, offset)

        is_partitioned = 0
        is_creative = False
        if save_version >= 13:
            is_partitioned, offset = read_uint32(data, offset)
            _, offset = read_uint32(data, offset)  # redundant confirm byte
            _, offset = read_uint64(data, offset)  # hash 1
            _, offset = read_uint64(data, offset)  # hash 2
            is_creative_val, offset = read_uint32(data, offset)
            is_creative = is_creative_val != 0

        self.header = {
            "save_version": save_version,
            "build_version": build_version,
            "save_name": save_name,
            "map_name": map_name,
            "map_options": map_options,
            "session_name": session_name,
            "play_duration_seconds": play_duration,
            "save_datetime": save_datetime,
            "session_visibility": session_visibility,
            "is_modded": is_modded != 0,
            "is_creative": is_creative,
            "is_partitioned": is_partitioned != 0,
        }
        return offset

    def _decompress_body(self, data: bytes, offset: int) -> bytes:
        decompressed = bytearray()
        while offset < len(data):
            sig, offset = read_uint32(data, offset)
            if sig != 0x9E2A83C1:
                raise ParseError(f"Invalid Unreal package signature {hex(sig)} at offset {offset - 4}")

            _, offset = read_uint32(data, offset)  # 0x22222222
            _, offset = read_uint8(data, offset)  # 0
            _, offset = read_uint32(data, offset)  # maximumChunkSize
            _, offset = read_uint32(data, offset)  # 0x03000000

            comp_len1, offset = read_uint64(data, offset)
            uncomp_len1, offset = read_uint64(data, offset)
            comp_len2, offset = read_uint64(data, offset)
            uncomp_len2, offset = read_uint64(data, offset)

            if comp_len1 != comp_len2 or uncomp_len1 != uncomp_len2:
                raise ParseError("Chunk size redundancy check failed")

            chunk_bytes = data[offset : offset + comp_len1]
            offset += comp_len1

            d_chunk = zlib.decompress(chunk_bytes)
            if len(d_chunk) != uncomp_len1:
                raise ParseError(f"Decompressed chunk length {len(d_chunk)} != expected {uncomp_len1}")

            decompressed.extend(d_chunk)
        return bytes(decompressed)

    def _parse_payload(self):
        data = self._decompressed_data
        offset = 0

        # Uncompressed size
        _uncomp_size, offset = read_uint64(data, offset)

        save_version = self.header["save_version"]
        ue5_version = -1
        if save_version >= 53:
            version_data, offset = read_version_data(data, offset)
            ue5_version = version_data["ue5_version"]

        # Partitions
        partition_count, offset = read_uint32(data, offset)
        for _ in range(partition_count):
            _, offset = read_string(data, offset)  # partitionName
            _, offset = read_uint32(data, offset)
            _, offset = read_uint32(data, offset)
            levels_count, offset = read_uint32(data, offset)
            for _ in range(levels_count):
                _, offset = read_string(data, offset)
                _, offset = read_uint32(data, offset)

        # Levels
        level_count, offset = read_uint32(data, offset)
        levels_headers = []
        levels_objects = {}
        self.collected_objects = []

        for _ in range(level_count):
            level_headers, level_objs, level_collectables, offset = self._parse_level(data, offset, False, ue5_version)
            levels_headers.extend(level_headers)
            levels_objects.update(level_objs)
            self.collected_objects.extend(level_collectables)

        # Persistent Level (main level)
        persistent_headers, persistent_objs, persistent_collectables, offset = self._parse_level(
            data, offset, True, ue5_version
        )
        levels_headers.extend(persistent_headers)
        levels_objects.update(persistent_objs)
        self.collected_objects.extend(persistent_collectables)

        # Map Player States to Player Characters
        self._extract_players_and_inventories(levels_headers, levels_objects)

        # Extract Milestones / Schematics from SchematicManager
        self._extract_schematics(levels_objects)

        # Extract Dimensional Depot
        self._extract_dimensional_depot(levels_objects)

        # Extract Game Phase
        self._extract_game_phase(levels_objects)

        # Extract Unlocked Recipes
        self._extract_recipes(levels_objects)

        # Extract MAM Research Trees
        self._extract_mam_research(levels_objects)

        # Extract Resource Sink progress
        self._extract_resource_sink(levels_objects)

        # Extract Vehicles list
        self._extract_vehicles(levels_headers)

        # Extract Factory Floor Buildings
        self._extract_factory_buildings(levels_headers, levels_objects)

        # Save raw objects for diagnostic queries
        self.levels_objects = levels_objects

    def _parse_level(
        self, data: bytes, offset: int, is_persistent: bool, ue5_version: int
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str], int]:
        save_version = self.header["save_version"]
        if DEBUG_PARSER:
            print(f"DEBUG _parse_level start: offset={offset}, is_persistent={is_persistent}")
        if not is_persistent:
            l_name, offset = read_string(data, offset)  # levelName
            if DEBUG_PARSER:
                print(f"DEBUG levelName={l_name}")

        obj_header_size, offset = read_uint64(data, offset)
        if DEBUG_PARSER:
            print(f"DEBUG obj_header_size={obj_header_size}")
        start_offset = offset

        actor_count, offset = read_uint32(data, offset)
        if actor_count > len(data) - offset:
            raise ParseError(f"Unreasonably large actor_count: {actor_count}")
        if DEBUG_PARSER:
            print(f"DEBUG actor_count={actor_count}")
        headers: list[dict[str, Any]] = []

        for _idx in range(actor_count):
            header_type, offset = read_uint32(data, offset)  # 1 = Actor, 0 = Component
            type_path, offset = read_string(data, offset)
            root_obj, offset = read_string(data, offset)
            instance_name, offset = read_string(data, offset)
            flags, offset = read_uint32(data, offset)

            header = {
                "header_type": header_type,
                "type_path": type_path,
                "root_object": root_obj,
                "instance_name": instance_name,
                "flags": flags,
                "position": [0.0, 0.0, 0.0],
            }

            if header_type == 1:
                # Actor properties
                _need_transform, offset = read_uint32(data, offset)
                # rotation (4 floats)
                _r_x, offset = read_float(data, offset)
                _r_y, offset = read_float(data, offset)
                _r_z, offset = read_float(data, offset)
                _r_w, offset = read_float(data, offset)
                header["rotation"] = [_r_x, _r_y, _r_z, _r_w]
                # position (3 floats)
                p_x, offset = read_float(data, offset)
                p_y, offset = read_float(data, offset)
                p_z, offset = read_float(data, offset)
                header["position"] = [p_x, p_y, p_z]
                # scale (3 floats)
                _, offset = read_float(data, offset)
                _, offset = read_float(data, offset)
                _, offset = read_float(data, offset)

                _, offset = read_uint32(data, offset)  # wasPlacedInLevel
            else:
                # Component properties
                _, offset = read_string(data, offset)  # parentActorName

            headers.append(header)

        if is_persistent:
            persistent_flag, offset = read_uint32(data, offset)
            if persistent_flag != 0:
                _, offset = read_string(data, offset)  # "Persistent_Level"

        collected_refs = []
        # Skip collectables 1 if size mismatch
        size_read = offset - start_offset
        if DEBUG_PARSER:
            print(f"DEBUG size_read={size_read}, obj_header_size={obj_header_size}")
        if obj_header_size != size_read:
            collected_count, offset = read_uint32(data, offset)
            if collected_count > len(data) - offset:
                raise ParseError(f"Unreasonably large collected_count: {collected_count}")
            if DEBUG_PARSER:
                print(f"DEBUG collected_count={collected_count}")
            for _ in range(collected_count):
                ref, offset = read_object_ref(data, offset)
                collected_refs.append(ref["path"])

        # Objects content
        objects_size, offset = read_uint64(data, offset)
        if DEBUG_PARSER:
            print(f"DEBUG objects_size={objects_size}")
        obj_start_offset = offset

        objects_data = {}
        obj_count, offset = read_uint32(data, offset)
        if obj_count > len(data) - offset:
            raise ParseError(f"Unreasonably large obj_count: {obj_count}")
        if DEBUG_PARSER:
            print(f"DEBUG obj_count={obj_count}, offset after count={offset}")
        for i in range(obj_count):
            header = headers[i]
            instance_name = str(header["instance_name"])

            obj_game_ver, offset = read_uint32(data, offset)
            _should_migrate, offset = read_uint32(data, offset)
            obj_size, offset = read_uint32(data, offset)
            if DEBUG_PARSER:
                print(
                    f"DEBUG Object {i}: name={instance_name}, type_path={header['type_path']}, game_ver={obj_game_ver}, obj_size={obj_size}, offset after size={offset}"
                )
            if DEBUG_PARSER:
                hex_bytes = data[offset : offset + 40].hex(" ")
                print(f"DEBUG hex bytes at {offset}: {hex_bytes}")

            start_this = offset

            obj_ue5_ver = ue5_version
            next_offset = start_this + obj_size

            if obj_game_ver >= 53:
                # jump to serialize flag
                jump = start_this + obj_size
                serialize_ver_flag, jump = read_uint32(data, jump)
                if serialize_ver_flag != 0:
                    v_data, jump = read_version_data(data, jump)
                    obj_ue5_ver = v_data["ue5_version"]
                next_offset = jump
                if DEBUG_PARSER:
                    print(f"DEBUG Object {i} ue5_ver={obj_ue5_ver}, next_offset={next_offset}")

            if header["header_type"] == 1:
                # Actor component list
                parent_ref, offset = read_object_ref(data, offset)
                comp_count, offset = read_uint32(data, offset)
                if DEBUG_PARSER:
                    print(
                        f"DEBUG Actor {i} parent_ref={parent_ref}, comp_count={comp_count}, offset after comps={offset}"
                    )
                for c_idx in range(comp_count):
                    c_ref, offset = read_object_ref(data, offset)
                    if DEBUG_PARSER:
                        print(f"  c_ref {c_idx}={c_ref}")

            if obj_ue5_ver >= 1011:
                _, offset = read_uint8(data, offset)  # serializationControl (0)

            # Parse properties
            properties, offset = self._parse_properties(data, offset, obj_ue5_ver)

            objects_data[instance_name] = {
                "instance_name": instance_name,
                "type_path": header["type_path"],
                "position": header["position"],
                "rotation": header.get("rotation", [0.0, 0.0, 0.0, 1.0]),
                "properties": properties,
            }

            # Reset offset exactly to the end of the object size
            offset = next_offset

        # skip remaining level elements
        offset = obj_start_offset + objects_size
        level_save_ver, offset = read_uint32(data, offset)
        if DEBUG_PARSER:
            print(f"DEBUG level_save_ver={level_save_ver}, offset after ver={offset}")

        if not is_persistent:
            collected_count2, offset = read_uint32(data, offset)
            if collected_count2 > len(data) - offset:
                raise ParseError(f"Unreasonably large collected_count2: {collected_count2}")
            if DEBUG_PARSER:
                print(f"DEBUG collected_count2={collected_count2}, offset after count={offset}")
            for c_idx in range(collected_count2):
                ref, offset = read_object_ref(data, offset)
                if DEBUG_PARSER:
                    print(f"DEBUG collected_ref {c_idx}={ref}")
            if save_version >= 53:
                has_ver, offset = read_uint32(data, offset)
                if DEBUG_PARSER:
                    print(f"DEBUG has_ver={has_ver}")
                if has_ver != 0:
                    _, offset = read_version_data(data, offset)

        return headers, objects_data, collected_refs, offset

    def _parse_properties(self, data: bytes, offset: int, ue5_version: int) -> tuple[dict[str, Any], int]:
        properties = {}
        while True:
            prop_name, offset = read_string(data, offset)
            if prop_name == "None" or not prop_name:
                break

            prop_type, offset = read_string(data, offset)

            header_flag = ue5_version >= 1012
            array_type = None
            struct_type = None
            enum_type = None

            if header_flag:
                header_a, offset = read_uint32(data, offset)
                if DEBUG_PARSER:
                    print(f"DEBUG prop={prop_name}, type={prop_type}, header_a={header_a}")
                if header_a == 1:
                    if prop_type == "ArrayProperty":
                        array_type, offset = read_string(data, offset)
                        header_b, offset = read_uint32(data, offset)
                        if header_b == 1:
                            struct_type, offset = read_string(data, offset)
                            _, offset = read_package_names(data, offset)
                        elif header_b == 2:
                            enum_type, offset = read_string(data, offset)
                            _, offset = read_package_names(data, offset)
                            _, offset = read_string(data, offset)  # ByteProperty
                            _, offset = read_uint32(data, offset)
                    elif prop_type == "ByteProperty":
                        enum_type, offset = read_string(data, offset)
                        _, offset = read_package_names(data, offset)
                    elif prop_type == "SetProperty":
                        _, offset = read_string(data, offset)
                        _, offset = read_package_names(data, offset)
                    elif prop_type == "StructProperty":
                        struct_type, offset = read_string(data, offset)
                        _, offset = read_package_names(data, offset)
                elif header_a == 2:
                    if prop_type == "EnumProperty":
                        enum_type, offset = read_string(data, offset)
                        _, offset = read_package_names(data, offset)
                        _, offset = read_string(data, offset)  # "ByteProperty"
                        _, offset = read_uint32(data, offset)  # 0
                    elif prop_type == "MapProperty":
                        _k_type, offset = read_string(data, offset)
                        has_key_type_name, offset = read_uint32(data, offset)
                        if has_key_type_name != 0:
                            _, offset = read_string(data, offset)
                            _, offset = read_package_names(data, offset)
                        _v_type, offset = read_string(data, offset)
                        has_val_type_name, offset = read_uint32(data, offset)
                        if has_val_type_name != 0:
                            _, offset = read_string(data, offset)
                            _, offset = read_package_names(data, offset)

            prop_size, offset = read_uint32(data, offset)

            if not header_flag:
                _, offset = read_uint32(data, offset)  # property index

            # Parse property headers and determine start_val_offset
            if prop_type == "StructProperty":
                if not header_flag:
                    struct_type, offset = read_string(data, offset)
                    _, offset = read_uint64(data, offset)  # uuid1
                    _, offset = read_uint64(data, offset)  # uuid2
                st_index, offset = read_uint8(data, offset)
                if st_index == 9:
                    _, offset = read_uint32(data, offset)
            elif prop_type == "ArrayProperty":
                if not header_flag:
                    array_type, offset = read_string(data, offset)
                _, offset = read_uint8(data, offset)  # zeroOrEight
            elif prop_type == "SetProperty":
                if not header_flag:
                    _, offset = read_string(data, offset)
                _, offset = read_uint8(data, offset)  # zeroOrEight
            elif prop_type == "MapProperty":
                if not header_flag:
                    _, offset = read_string(data, offset)  # keyType
                    _, offset = read_string(data, offset)  # valueType
                _, offset = read_uint8(data, offset)  # zeroOrEight
            else:
                # Other properties have a 1-byte GUID confirmation byte
                _, offset = read_uint8(data, offset)

            start_val_offset = offset
            if DEBUG_PARSER:
                print(
                    f"  PROP: name={prop_name}, type={prop_type}, size={prop_size}, start_val_offset={start_val_offset}"
                )
            val: Any = None

            try:
                if prop_type == "BoolProperty":
                    b_val, offset = read_uint8(data, offset)
                    val = b_val != 0
                elif prop_type == "IntProperty":
                    val, offset = read_int32(data, offset)
                elif prop_type == "FloatProperty":
                    val, offset = read_float(data, offset)
                elif prop_type == "DoubleProperty":
                    val, offset = read_double(data, offset)
                elif prop_type in ("StrProperty", "NameProperty"):
                    val, offset = read_string(data, offset)
                elif prop_type == "ObjectProperty":
                    val, offset = read_object_ref(data, offset)
                elif prop_type == "EnumProperty":
                    if DEBUG_PARSER:
                        h_bytes = data[offset : offset + 30].hex(" ")
                        temp_len, _ = read_int32(data, offset)
                        print(f"DEBUG EnumProperty val hex={h_bytes}, strlen={temp_len}")
                    val, offset = read_string(data, offset)
                    if DEBUG_PARSER:
                        print(f"DEBUG EnumProperty decoded={val}")
                elif prop_type == "ByteProperty":
                    if not header_flag:
                        enum_type, offset = read_string(data, offset)
                    if enum_type is None or enum_type == "None":
                        val, offset = read_uint8(data, offset)
                    else:
                        val, offset = read_string(data, offset)
                elif prop_type == "StructProperty":
                    if struct_type == "InventoryItem":
                        _, offset = read_uint32(data, offset)  # zero
                        item_name, offset = read_string(data, offset)
                        has_item_props, offset = read_uint32(data, offset)
                        item_props: dict[str, Any] = {}
                        if has_item_props != 0:
                            _, offset = read_uint32(data, offset)  # zero
                            _, offset = read_string(data, offset)  # typePath
                            _, offset = read_uint32(data, offset)  # size
                            item_props, offset = self._parse_properties(data, offset, ue5_version)
                        val = {"item_name": item_name, "properties": item_props}
                    elif struct_type == "LinearColor":
                        r, offset = read_float(data, offset)
                        g, offset = read_float(data, offset)
                        b, offset = read_float(data, offset)
                        a, offset = read_float(data, offset)
                        val = [r, g, b, a]
                    elif struct_type in ("Vector", "Rotator"):
                        x, offset = read_double(data, offset)
                        y, offset = read_double(data, offset)
                        z, offset = read_double(data, offset)
                        val = [x, y, z]
                    elif struct_type == "Vector2D":
                        x, offset = read_double(data, offset)
                        y, offset = read_double(data, offset)
                        val = [x, y]
                    else:
                        # Parse nested properties for custom structs
                        val, offset = self._parse_properties(data, offset, ue5_version)
                elif prop_type == "ArrayProperty":
                    array_count, offset = read_uint32(data, offset)
                    if array_count > len(data) - offset:
                        raise ParseError(f"Unreasonably large array_count: {array_count}")
                    val = []

                    if array_type == "IntProperty":
                        for _ in range(array_count):
                            i_val, offset = read_int32(data, offset)
                            val.append(i_val)
                    elif array_type in ("StrProperty", "EnumProperty"):
                        for _ in range(array_count):
                            s_val, offset = read_string(data, offset)
                            val.append(s_val)
                    elif array_type in ("ObjectProperty", "InterfaceProperty"):
                        for _ in range(array_count):
                            o_ref, offset = read_object_ref(data, offset)
                            val.append(o_ref)
                    elif array_type == "StructProperty":
                        if not header_flag:
                            _, offset = read_string(data, offset)  # struct name
                            _, offset = read_string(data, offset)  # "StructProperty"
                            _, offset = read_uint32(data, offset)  # size
                            _, offset = read_uint32(data, offset)  # zero
                            struct_type, offset = read_string(data, offset)
                            _, offset = read_bytes(data, offset, 17)  # uuid

                        if struct_type == "LinearColor":
                            for _ in range(array_count):
                                r, offset = read_float(data, offset)
                                g, offset = read_float(data, offset)
                                b, offset = read_float(data, offset)
                                a, offset = read_float(data, offset)
                                val.append([r, g, b, a])
                        elif struct_type == "Vector":
                            for _ in range(array_count):
                                x, offset = read_double(data, offset)
                                y, offset = read_double(data, offset)
                                z, offset = read_double(data, offset)
                                val.append([x, y, z])
                        else:
                            for _ in range(array_count):
                                struct_val, offset = self._parse_properties(data, offset, ue5_version)
                                val.append(struct_val)
            except Exception as e:
                # Silently catch and recover by aligning offset
                if prop_name in (
                    "mPurchasedSchematics",
                    "mAvailableRecipes",
                    "mUnlockedResearchTrees",
                    "mInventoryStacks",
                ):
                    print(f"DEBUG Error parsing property {prop_name}: {e}")
                    import traceback

                    traceback.print_exc()

            offset = start_val_offset + prop_size
            properties[prop_name] = val

        return properties, offset

    def _extract_players_and_inventories(self, headers: list[dict[str, Any]], objects: dict[str, dict[str, Any]]):
        # 1. Locate BP_PlayerState instances to get usernames and owned pawns
        player_states: dict[str, dict[str, Any]] = {}
        # Decode the default name from map options
        default_name = "Unknown Player"
        map_options = self.header.get("map_options", "")
        if map_options:
            parts = map_options.split("?")
            snapshot_hex = None
            for part in parts:
                if part.startswith("PlayerInfoSnapshot="):
                    snapshot_hex = part.split("=")[1]
                    break
            if snapshot_hex:
                try:
                    snapshot_data = bytes.fromhex(snapshot_hex)
                    p_offset = 0
                    _, p_offset = read_string(snapshot_data, p_offset)  # platform
                    _, p_offset = read_string(snapshot_data, p_offset)  # None
                    p_offset += 18  # skip platform ID bytes
                    snapshot_name, _ = read_string(snapshot_data, p_offset)
                    if snapshot_name:
                        default_name = snapshot_name
                except Exception:
                    pass

        # 1. Locate BP_PlayerState instances to get usernames and owned pawns
        player_states = {}
        for obj_name, obj in objects.items():
            if "BP_PlayerState" in obj["type_path"]:
                username = obj["properties"].get("mCachedPlayerName", default_name)
                if not username or username == "None" or username == "Unknown Player":
                    username = default_name
                owned_pawn = obj["properties"].get("mOwnedPawn")
                if owned_pawn:
                    player_states[owned_pawn["path"]] = {"username": username, "player_state_path": obj_name}

        # 2. Match with Char_Player actors to get positions and inventories
        for obj_name, obj in objects.items():
            if "Char_Player" in obj["type_path"]:
                player_info = player_states.get(obj_name, {"username": default_name, "player_state_path": ""})

                # Fetch position from ActorHeader
                position = obj["position"]

                # Fetch inventory reference
                inventory_ref = obj["properties"].get("mInventory")
                inventory_items = []
                if inventory_ref:
                    inv_obj = objects.get(inventory_ref["path"])
                    if inv_obj:
                        stacks = inv_obj["properties"].get("mInventoryStacks", [])
                        if stacks is None:
                            stacks = []
                        for stack in stacks:
                            if not stack:
                                continue
                            item_prop = stack.get("Item")
                            num_items = stack.get("NumItems", 0)
                            if item_prop and item_prop.get("item_name"):
                                clean_name = item_prop["item_name"].split(".")[-1].removesuffix("_C")
                                inventory_items.append(
                                    {"item_id": item_prop["item_name"], "name": clean_name, "quantity": num_items}
                                )

                self.players.append(
                    {
                        "username": player_info["username"],
                        "character_path": obj_name,
                        "position": position,
                        "inventory": inventory_items,
                    }
                )

    def _extract_schematics(self, objects: dict[str, dict[str, Any]]):
        self.hard_drives_unlocked = 0
        # Extract purchased schematics (milestones)
        for obj_name, obj in objects.items():
            if "schematicManager" in obj_name.lower() or "SchematicManager" in obj["type_path"]:
                purchased = obj["properties"].get("mPurchasedSchematics", [])
                if purchased is None:
                    purchased = []
                for ref in purchased:
                    if isinstance(ref, dict) and ref.get("path"):
                        path = ref["path"]
                        schem_name = path.split(".")[-1].removesuffix("_C")
                        self.schematics.append(schem_name)
                        if "Schematic_Alternate_" in path or "/Alternate/" in path:
                            self.hard_drives_unlocked += 1
                # Also capture active schematic as metadata
                active_ref = obj["properties"].get("mActiveSchematic")
                if active_ref and isinstance(active_ref, dict) and active_ref.get("path"):
                    active_name = active_ref["path"].split(".")[-1].removesuffix("_C")
                    self.metadata["active_schematic"] = active_name
                break

    def _extract_dimensional_depot(self, objects: dict[str, dict[str, Any]]):
        self.dimensional_depot = []
        for obj_name, obj in objects.items():
            if "CentralStorageSubsystem" in obj_name or "CentralStorageSubsystem" in obj.get("type_path", ""):
                stored_items = obj["properties"].get("mStoredItems", [])
                if stored_items is None:
                    stored_items = []
                for stored_item in stored_items:
                    if not stored_item:
                        continue
                    item_class = stored_item.get("ItemClass") or stored_item.get("itemClass")
                    amount = stored_item.get("amount") or stored_item.get("Amount") or 0
                    if item_class and item_class.get("path"):
                        item_id = item_class["path"]
                        clean_name = item_id.split(".")[-1].removesuffix("_C")
                        self.dimensional_depot.append(
                            DimensionalDepotItem(item_id=item_id, name=clean_name, quantity=amount)
                        )
                break

    def _extract_game_phase(self, objects: dict[str, dict[str, Any]]):
        self.game_phase = "Unknown"
        for obj_name, obj in objects.items():
            if "GamePhaseManager" in obj_name or "GamePhaseManager" in obj.get("type_path", ""):
                phase_ref = obj["properties"].get("mCurrentGamePhase")
                if phase_ref and isinstance(phase_ref, dict) and phase_ref.get("path"):
                    self.game_phase = phase_ref["path"].split(".")[-1].removesuffix("_C")
                break

    @property
    def collected_collectibles_summary(self) -> dict[str, int]:
        summary = {
            "somersloop": 0,
            "mercer_sphere": 0,
            "power_slug_blue": 0,
            "power_slug_yellow": 0,
            "power_slug_purple": 0,
        }
        for path in self.collected_objects:
            path_lower = path.lower()
            if "somersloop" in path_lower or "bp_wat" in path_lower or "wat" in path_lower:
                summary["somersloop"] += 1
            elif "mercer" in path_lower:
                summary["mercer_sphere"] += 1
            elif "crystal" in path_lower:
                if "mk2" in path_lower:
                    summary["power_slug_yellow"] += 1
                elif "mk3" in path_lower:
                    summary["power_slug_purple"] += 1
                else:
                    summary["power_slug_blue"] += 1
        return summary

    def _extract_recipes(self, objects: dict[str, dict[str, Any]]):
        self.recipes = []
        self.alternate_recipes_unlocked = 0
        for obj_name, obj in objects.items():
            if "recipeManager" in obj_name.lower() or "RecipeManager" in obj.get("type_path", ""):
                available = obj["properties"].get("mAvailableRecipes", [])
                if available is None:
                    available = []
                for ref in available:
                    if isinstance(ref, dict) and ref.get("path"):
                        path = ref["path"]
                        recipe_name = path.split(".")[-1].removesuffix("_C")
                        self.recipes.append(recipe_name)
                        if "Recipe_Alternate_" in path or "/Alternate/" in path:
                            self.alternate_recipes_unlocked += 1
                break

    def _extract_mam_research(self, objects: dict[str, dict[str, Any]]):
        self.unlocked_research_trees = []
        for obj_name, obj in objects.items():
            if "researchManager" in obj_name.lower() or "ResearchManager" in obj.get("type_path", ""):
                unlocked = obj["properties"].get("mUnlockedResearchTrees", [])
                if unlocked is None:
                    unlocked = []
                for ref in unlocked:
                    if isinstance(ref, dict) and ref.get("path"):
                        path = ref["path"]
                        tree_name = path.split(".")[-1].removesuffix("_C")
                        self.unlocked_research_trees.append(tree_name)
                break

    def _extract_resource_sink(self, objects: dict[str, dict[str, Any]]):
        self.resource_sink = {
            "total_points_items": 0,
            "total_points_dna": 0,
            "coupons_earned_items": 0,
            "coupons_earned_dna": 0,
            "coupons_available": 0,
        }
        for obj_name, obj in objects.items():
            if (
                obj_name == "Persistent_Level:PersistentLevel.ResourceSinkSubsystem"
                or "ResourceSinkSubsystem" in obj.get("type_path", "")
            ):
                props = obj["properties"]
                total = props.get("mTotalPoints")
                if total and isinstance(total, list) and len(total) == 2:
                    self.resource_sink["total_points_items"] = total[0]
                    self.resource_sink["total_points_dna"] = total[1]

                levels = props.get("mCurrentPointLevels")
                if levels and isinstance(levels, list) and len(levels) == 2:
                    self.resource_sink["coupons_earned_items"] = levels[0]
                    self.resource_sink["coupons_earned_dna"] = levels[1]

                self.resource_sink["coupons_available"] = props.get("mNumResourceSinkCoupons") or 0
                break

    def _extract_vehicles(self, headers: list[dict[str, Any]]):
        self.vehicles = {}
        for h in headers:
            type_path = h.get("type_path", "")
            if "/Vehicle/" in type_path:
                class_name = type_path.split(".")[-1].removesuffix("_C")
                readable = class_name.replace("BP_", "")
                # Map specific vehicle names to nicer ones
                mapping = {"Golfcart": "Factory Cart", "Cyberwagon": "Cyber Wagon", "CargoWagon": "Cargo Wagon"}
                readable = mapping.get(readable, readable)
                self.vehicles[readable] = self.vehicles.get(readable, 0) + 1

    def _extract_factory_buildings(self, headers: list[dict[str, Any]], objects: dict[str, dict[str, Any]]):
        self.factory_producers = {}
        self.factory_extractors = {}
        self.factory_generators = {}
        self.factory_batteries = 0

        for h in headers:
            type_path = h.get("type_path", "")
            if not type_path or "/Build_" not in type_path:
                continue

            class_name = type_path.split(".")[-1].removesuffix("_C")

            if "Build_PowerStorage" in class_name:
                self.factory_batteries += 1
            elif "Build_Generator" in class_name:
                readable = class_name.replace("Build_Generator", "")
                mapping = {
                    "Biomass": "Biomass Generator",
                    "BiomassIntegrated": "Integrated Biomass Generator",
                    "Coal": "Coal Generator",
                    "Fuel": "Fuel Generator",
                    "Nuclear": "Nuclear Power Plant",
                    "GeoThermal": "Geothermal Generator",
                }
                readable = mapping.get(readable, readable or "Generator")
                self.factory_generators[readable] = self.factory_generators.get(readable, 0) + 1
            elif any(
                x in class_name for x in ("Build_Miner", "Build_OilPump", "Build_WaterPump", "Build_FrackingExtractor")
            ):
                readable = class_name.replace("Build_", "")
                if "MinerMk" in readable:
                    readable = readable.replace("MinerMk", "Miner Mk")
                elif "WaterPump" in readable:
                    readable = "Water Extractor"
                elif "OilPump" in readable:
                    readable = "Oil Extractor"
                elif "FrackingExtractor" in readable:
                    readable = "Resource Well Extractor"
                self.factory_extractors[readable] = self.factory_extractors.get(readable, 0) + 1
            elif any(
                x in class_name
                for x in (
                    "Build_Constructor",
                    "Build_Assembler",
                    "Build_Manufacturer",
                    "Build_Smelter",
                    "Build_Foundry",
                    "Build_OilRefinery",
                    "Build_Refinery",
                    "Build_Blender",
                    "Build_Packager",
                    "Build_ParticleAccelerator",
                    "Build_Converter",
                    "Build_QuantumEncoder",
                    "Build_HadronCollider",
                    "Build_Encoder",
                )
            ):
                readable = class_name.replace("Build_", "")
                if readable == "OilRefinery":
                    readable = "Refinery"
                self.factory_producers[readable] = self.factory_producers.get(readable, 0) + 1
