"""
tools/map_power.py

Parses the game save file to reconstruct the player's built power grid,
computes the Hover Pack coverage graph, outputs flyable routes,
and extracts world points of interest (nests, remains, drop pods, fauna).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

# Add project root to sys.path so we can import utils
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.cli import _find_latest_save_file  # noqa: E402
from utils.save_parser import SatisfactorySave  # noqa: E402


def dist_3d(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2)


def get_node_range(type_path):
    if "PowerTower" in type_path:
        return 15000.0  # 150m for Power Towers
    return 3000.0  # 30m standard Hover Pack range


def generate_power_map():
    save_path = _find_latest_save_file()
    if not save_path:
        print("Error: No save file found.")
        return None

    print(f"Loading save: {save_path}")
    save = SatisfactorySave(save_path)

    if not save.players:
        print("Error: No player found in save.")
        return None

    player = save.players[0]
    player_pos = player["position"]
    print(
        f"Player: '{player['username']}' at coordinates: X={player_pos[0]:.1f}, Y={player_pos[1]:.1f}, Z={player_pos[2]:.1f}"
    )

    # Extract all Build_ objects as potential power nodes
    nodes = {}
    pois = {
        "lizard_doggos": [],
        "drop_pods": [],
        "enemy_nests": [],
        "enemy_remains": [],
        "resource_nodes": [],
        "geysers": [],
    }

    for name, obj in save.levels_objects.items():
        t_path = obj.get("type_path", "")
        class_name = t_path.split(".")[-1].removesuffix("_C")
        pos = obj.get("position", [0.0, 0.0, 0.0])
        props = obj.get("properties", {}) or {}

        # 1. Power grid nodes
        if "/Build_" in t_path and "Build_PowerLine" not in t_path:
            nodes[name] = {"id": name, "type": class_name, "pos": pos, "range": get_node_range(t_path)}

        # 2. Points of interest / hazards
        elif class_name == "Char_SpaceRabbit":
            pois["lizard_doggos"].append({"id": name, "pos": pos, "properties": props})
        elif class_name == "BP_DropPod":
            pois["drop_pods"].append({"id": name, "pos": pos, "properties": props})
        elif class_name in ("Char_CrabHatcher", "Char_BigCrabHatcher"):
            pois["enemy_nests"].append({"id": name, "type": class_name.replace("Char_", ""), "pos": pos})
        elif "parts" in class_name.lower() and (
            "hog" in class_name.lower() or "spitter" in class_name.lower() or "stinger" in class_name.lower()
        ):
            pois["enemy_remains"].append(
                {"id": name, "type": class_name.replace("BP_", "").replace("Parts", ""), "pos": pos}
            )
        elif class_name == "BP_ResourceNode" and "Geyser" not in t_path:
            res_item = props.get("mRepresentedItem", "") or props.get("mExtractableResource", "")
            res_type = "Unknown"
            if res_item:
                res_type = res_item.split(".")[-1].removesuffix("_C").replace("Desc_", "").replace("Ore", "")
            pois["resource_nodes"].append(
                {"id": name, "purity": props.get("mPurityOverride", "RP_Normal"), "pos": pos, "type": res_type}
            )
        elif class_name == "BP_ResourceNodeGeyser":
            pois["geysers"].append({"id": name, "pos": pos})

    # Track extractors list from nodes
    extractors = []
    for name, node in nodes.items():
        c_name = node["type"]
        if "Miner" in c_name or "Extractor" in c_name or "WaterPump" in c_name or "GeneratorGeyser" in c_name:
            extractors.append({"id": name, "type": c_name, "pos": node["pos"]})

    for node in pois["resource_nodes"]:
        node["extracted"] = False
        node["extractor_type"] = ""
        for ext in extractors:
            if dist_3d(node["pos"], ext["pos"]) < 1000.0:
                node["extracted"] = True
                node["extractor_type"] = ext["type"]
                break

    for geyser in pois["geysers"]:
        geyser["extracted"] = False
        geyser["extractor_type"] = ""
        for ext in extractors:
            if dist_3d(geyser["pos"], ext["pos"]) < 1000.0:
                geyser["extracted"] = True
                geyser["extractor_type"] = ext["type"]
                break

    print(f"Extracted {len(nodes)} candidate power structures.")

    # Extract all Power Wires
    lines = []
    for name, obj in save.levels_objects.items():
        if "Build_PowerLine" in obj.get("type_path", ""):
            lines.append(
                {"id": name, "midpoint": obj["position"], "length": obj["properties"].get("mCachedLength", 0.0)}
            )

    print(f"Extracted {len(lines)} power wires. Reconstructing connectivity...")

    node_list = list(nodes.values())
    node_positions = np.array([n["pos"] for n in node_list])

    connections = {n["id"]: [] for n in node_list}
    matched_lines = []

    for line in lines:
        M = np.array(line["midpoint"])
        L = line["length"]

        # Source is the node closest to the wire midpoint actor position
        dists_to_M = np.linalg.norm(node_positions - M, axis=1)
        idx_a = np.argmin(dists_to_M)
        A = node_positions[idx_a]

        # Target is the node whose distance to A is closest to wire length L
        dists_to_A = np.linalg.norm(node_positions - A, axis=1)
        errors = np.abs(dists_to_A - L)
        idx_b = np.argmin(errors)

        # Validate match (error should be within 5 meters)
        if errors[idx_b] < 500.0 and idx_a != idx_b:
            node_a = node_list[idx_a]
            node_b = node_list[idx_b]

            connections[node_a["id"]].append(node_b["id"])
            connections[node_b["id"]].append(node_a["id"])

            matched_lines.append(
                {
                    "id": line["id"],
                    "node_a": node_a["id"],
                    "node_b": node_b["id"],
                    "length": L,
                    "midpoint": line["midpoint"],
                }
            )

    print(f"Reconstructed {len(matched_lines)} wires geometrically.")

    # Filter active grid nodes
    active_nodes = {n_id: n for n_id, n in nodes.items() if connections[n_id]}
    print(f"Active power grid network: {len(active_nodes)} connected nodes.")

    # Find the closest active power node to the player
    nearest_node = None
    min_dist_to_player = float("inf")
    for n in active_nodes.values():
        d = dist_3d(player_pos, n["pos"])
        if d < min_dist_to_player:
            min_dist_to_player = d
            nearest_node = n

    is_powered = False
    if nearest_node:
        is_powered = min_dist_to_player <= nearest_node["range"]

    print(
        f"Nearest active power source: {nearest_node['type'] if nearest_node else 'None'} ({min_dist_to_player / 100.0:.1f}m away)"
    )
    print(f"Player is currently powered by Hover Pack: {'YES' if is_powered else 'NO'}")

    # BFS from nearest node to map the connected component (Reachable Grid)
    reachable_nodes = {}
    if nearest_node and is_powered:
        queue = [nearest_node["id"]]
        visited = set(queue)

        while queue:
            curr = queue.pop(0)
            reachable_nodes[curr] = active_nodes[curr]
            for neighbor in connections[curr]:
                if neighbor in active_nodes and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

    print(f"Reachable Hover Pack grid from player position: {len(reachable_nodes)} / {len(active_nodes)} nodes.")

    # Reconstruct reachable wires
    reachable_wires = []
    for w in matched_lines:
        if w["node_a"] in reachable_nodes and w["node_b"] in reachable_nodes:
            reachable_wires.append(w)

    total_wire_length = sum(w["length"] for w in reachable_wires) / 100.0

    # Generate stats report
    stats = {
        "generated_at": str(Path(save_path).stat().st_mtime),
        "save_file": str(save_path),
        "player_position": player_pos,
        "nearest_node_distance_meters": min_dist_to_player / 100.0,
        "is_currently_powered": is_powered,
        "total_active_nodes": len(active_nodes),
        "total_wires": len(matched_lines),
        "reachable_nodes_count": len(reachable_nodes),
        "reachable_wires_count": len(reachable_wires),
        "reachable_network_length_meters": total_wire_length,
    }

    # Generate exploration route suggestions along straight paths (chains)
    suggested_routes = generate_route_suggestions(reachable_nodes, connections, player_pos)

    # Save outputs
    stats_dir = project_root / "stats"
    stats_dir.mkdir(exist_ok=True)

    # Save power map and suggested routes
    out_file = stats_dir / "power_map.json"
    map_data = {
        "stats": stats,
        "reachable_nodes": list(reachable_nodes.values()),
        "reachable_wires": reachable_wires,
        "suggested_routes": suggested_routes,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(map_data, f, indent=2, ensure_ascii=False)

    # Save detailed world POIs and hazards
    poi_file = stats_dir / "spatial_data.json"
    poi_data = {"stats": stats, "points_of_interest": pois}
    with open(poi_file, "w", encoding="utf-8") as f:
        json.dump(poi_data, f, indent=2, ensure_ascii=False)

    print(f"Map data saved to {out_file.absolute()}")
    print(f"Spatial POIs & hazards data saved to {poi_file.absolute()}")

    return {"map": map_data, "pois": pois}


def generate_route_suggestions(reachable_nodes, connections, player_pos):
    if not reachable_nodes:
        return []

    sorted_nodes = sorted(reachable_nodes.values(), key=lambda n: dist_3d(player_pos, n["pos"]))
    routes = []
    visited_in_routes = set()

    for start_node in sorted_nodes[:3]:
        if start_node["id"] in visited_in_routes:
            continue

        chain = []
        curr = start_node["id"]

        while curr:
            chain.append(reachable_nodes[curr])
            visited_in_routes.add(curr)

            next_node = None
            for neighbor in connections[curr]:
                if neighbor in reachable_nodes and neighbor not in visited_in_routes:
                    next_node = neighbor
                    break
            curr = next_node

        if len(chain) >= 3:
            legs = []
            curr_pos = player_pos

            for i, target in enumerate(chain):
                dx = target["pos"][0] - curr_pos[0]
                dy = target["pos"][1] - curr_pos[1]
                dz = target["pos"][2] - curr_pos[2]
                distance = math.sqrt(dx**2 + dy**2 + dz**2)

                duration = max(1.0, round(distance / 950.0, 1))

                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)

                legs.append(
                    {
                        "target_pole_type": target["type"],
                        "distance_meters": round(distance / 100.0, 1),
                        "keys": ["w", "space"] if i > 0 else ["w"],
                        "duration": duration,
                        "direction_yaw": round(angle_deg, 1),
                    }
                )
                curr_pos = target["pos"]

            routes.append(
                {
                    "name": f"Chain from nearest {start_node['type']}",
                    "total_legs": len(legs),
                    "total_distance_meters": round(sum(leg["distance_meters"] for leg in legs), 1),
                    "legs": legs,
                }
            )

    return routes


if __name__ == "__main__":
    generate_power_map()
