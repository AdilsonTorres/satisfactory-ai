# Satisfactory Save Game Parser Specification

This document details the binary file format of Satisfactory save games (`.sav`) and documents the architecture, findings, and implementation of our pure, lightweight, dependency-free Python parser.

The parser implementation is located at [utils/save_parser.py](file:///home/adilson/Projects/github/satisfactory-ai/utils/save_parser.py).

---

## 1. Binary Save File Structure

A Satisfactory save file consists of two primary segments:
1. **Uncompressed Save Header**: Metadata about the game build, session name, visibility, and play duration.
2. **Compressed Body Chunks**: Core game state (actors, components, items, subsystems) packed into zlib-compressed chunks.

```
+------------------------------------------+
|  SaveFileInfo Header (Uncompressed)      |
+------------------------------------------+
|  Compressed Chunk 1 (zlib)               |
|  - Compressed size                       |
|  - Uncompressed size                     |
|  - Compressed byte block                 |
+------------------------------------------+
|  Compressed Chunk 2 (zlib)               |
|  ...                                     |
+------------------------------------------+
```

---

## 2. Header Deserialization

The uncompressed header starts at byte offset `0` and contains:

| Data Type | Field Name | Description |
| :--- | :--- | :--- |
| `int32` | `save_version` | Serialized file version (currently `60` in v1.0). |
| `int32` | `build_version` | Satisfactory game engine build version number. |
| `string` | `map_name` | Name of the Unreal level map (usually `Persistent_Level`). |
| `string` | `map_options` | Query parameters containing player info and client ID. |
| `string` | `session_name` | Name of the save session. |
| `int32` | `play_duration` | Session duration in seconds. |
| `int64` | `save_datetime` | Timestamp when the save was created. |
| `uint8` | `session_visibility` | 0 = Private, 1 = Friends Only, etc. |
| `int32` | `editor_object_version` | (If save version >= 21) Engine version tracking. |
| `string` | `mod_metadata` | (If save version >= 43) Modding metadata. |
| `int32` | `is_modded` | (If save version >= 43) Modded game flag. |
| `int32` | `is_creative` | Creative mode flag. |
| `int32` | `is_partitioned` | (If save version >= 60) World partitioning flag. |

---

## 3. Payload Decompression

Following the header, the remaining file is read as a sequence of compressed chunks:
- Each chunk has an `int64` header specifying `magic_cookie`, `max_chunk_size`, `compressed_size`, and `uncompressed_size`.
- The payload bytes are inflated using standard `zlib.decompress` and concatenated into a single continuous memory block (`data`).

---

## 4. Object Level Grid Layout

The inflated payload is divided into levels (e.g. `Persistent_Level` and partitioned sub-grids). Each level block follows a strict serialization flow:

```
[Level Block]
  |--> levelName (string, if not persistent)
  |--> obj_header_size (uint64)
  |--> actor_count (uint32)
  |--> [Actor Headers List] (type, name, coordinates, rotation, scale)
  |--> collected_count (uint32)
  |--> [Collected References List]
  |--> objects_size (uint64)
  |--> obj_count (uint32)
  |--> [Object Body Content List] (Properties Map, custom payloads)
  |--> collected_count2 (uint32)
  |--> [Collected References List 2]
```

### Actor Header Layout
Each actor defined in the headers table is unpacked with:
- `type_path` (string)
- `instance_name` (string)
- `parent_actor_name` (string, if component class)
- `position` (`double[3]` XYZ coordinates)
- `rotation` (`double[4]` Quaternion XYZW)
- `scale` (`double[3]` XYZ scale)
- `was_placed_in_level` (`uint32`)

---

## 5. Property Deserialization (UE5 Format)

Each object's body content consists of serialized properties terminated by `"None\0"`.
For Unreal Engine 5 formats (`ue5_version >= 1012`), properties contain additional metadata headers based on a classification byte `header_a`:

### Metadata Structure
- **Type A = 1**:
  Used by `StructProperty`, `ArrayProperty`, `SetProperty`, and `ByteProperty`. Includes the inner element type string or struct subtype string (e.g., `InventoryStack`).
- **Type A = 2**:
  Used by `EnumProperty` and `MapProperty`. Includes key/value type definitions.
- **GUID Flag**:
  An additional `uint8` GUID confirmation byte is present for all properties **except** `StructProperty`, `ArrayProperty`, `SetProperty`, and `MapProperty`.

### Crucial Offset Findings & Fixes
1. **Property Size Boundaries**: The header specifies `prop_size` (total value size in bytes). If a parsing error occurs, we calculate the next offset as `start_val_offset + prop_size` to instantly align and recover.
2. **Double Header Reading**: Value deserialization blocks must *not* re-read inner types or flags already consumed during the metadata header block. Doing so causes offset misalignment (e.g., parsing a `StructProperty` array length as `83886080` instead of `1`).
3. **Out-of-Bounds Protection**: Added strict check limits on all counts read from the payload to prevent infinite allocation loops:
   ```python
   if count > len(data) - offset:
       raise ParseError(f"Unreasonably large count: {count}")
   ```

---

## 6. Game State Extraction Metrics

### A. Player Coordinates & Inventories
- **Actor pawns** of class `Char_Player` carry the physical location in the level and have an `mInventory` component.
- **Player states** (`BP_PlayerState`) contain player attributes like hotbar indices, visited areas, and client connections.
- **Player Names**: Real pioneer names are extracted by parsing the `PlayerInfoSnapshot` parameter inside `map_options`. It contains a hex-encoded binary snapshot which can be decoded to obtain the platform username (e.g. `Adilson`).

### B. Schematics & Milestones
- Unlocked milestones are tracked by `SchematicManager`.
- If Advanced Game Settings are used to "Unlock All", `mPurchasedSchematics` remains empty while `RecipeManager` (`mAvailableRecipes`) is populated with recipes directly.

---

## 7. Parser Usage Example

```python
from utils.save_parser import SatisfactorySave

# Load and parse the save game
save = SatisfactorySave("path/to/save.sav")

# Access metadata
print(f"Session Name: {save.header['session_name']}")
print(f"Play Duration: {save.header['play_duration_seconds']}s")

# Extract player information
for idx, player in enumerate(save.players, 1):
    print(f"Player #{idx}: {player['username']}")
    print(f"  Position: {player['position']}")
    print(f"  Inventory size: {len(player['inventory'])} stacks")
```
