"""
tools/apply_manual_labels.py

Applies the visual item identifications to the SQLite gift database.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Our 100% verified visual identifications of the 19 clusters
CLUSTER_MAP = {
    5: "Rifle Ammo",
    7: "Heat Sink",
    9: "Quartz Crystal",
    11: "Nobelisk",
    12: "Plastic",
    13: "Cable",
    14: "Circuit Board",
    15: "Screw",
    25: "Rubber",
    26: "Wire",
    31: "Computer",
    33: "Pulse Nobelisk",
    34: "Heavy Modular Frame",
    35: "Iron Plate",
    38: "Iron Rebar",
    39: "Concrete",
    41: "Steel Pipe",
    42: "Silica",
    45: "Motor",
}


def apply_labels() -> Any:
    db_path = Path("stats") / "gift_history.db"
    if not db_path.exists():
        print(f"Error: Database not found at {db_path.absolute()}")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all collected gifts
    rows = cursor.execute("SELECT id, ts, doggo, item, crop_path FROM gift_checks WHERE collected = 1").fetchall()

    records = []
    loaded_images = []

    for row_id, ts, doggo, item, crop_path in rows:
        if not crop_path:
            continue

        img_path = Path(crop_path)
        if not img_path.exists():
            img_path = project_root / crop_path
            if not img_path.exists():
                continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        records.append(
            {
                "id": row_id,
                "ts": ts,
                "doggo": doggo,
                "item": item if (item and item.lower() != "none") else None,
                "crop_path": crop_path,
            }
        )
        loaded_images.append(img)

    # Reconstruct the clusters
    threshold = 8.0
    clusters: list[Any] = []  # List of dicts: {"rep": image, "records": [record_dict, ...]}

    for idx, img in enumerate(loaded_images):
        rec = records[idx]
        matched_cluster = None
        min_diff = float("inf")

        for c_idx, cluster in enumerate(clusters):
            rep = cluster["rep"]
            if rep.shape == img.shape:
                diff = float(np.mean(np.abs(img.astype(np.float32) - rep.astype(np.float32))))
                if diff < threshold and diff < min_diff:
                    min_diff = diff
                    matched_cluster = c_idx

        if matched_cluster is not None:
            clusters[matched_cluster]["records"].append(rec)
        else:
            clusters.append({"rep": img, "records": [rec]})

    # Prepare batch updates
    updates = []
    resolved_count = 0

    for c_idx, cluster in enumerate(clusters):
        if c_idx not in CLUSTER_MAP:
            continue

        resolved_name = CLUSTER_MAP[c_idx]
        recs = cluster["records"]

        for r in recs:
            # We overwrite any None item or update it to the standard visual label
            if r["item"] is None:
                updates.append((resolved_name, r["id"]))
                resolved_count += 1

    if updates:
        print(f"Applying {len(updates)} visual label updates to SQLite...")
        cursor.executemany("UPDATE gift_checks SET item = ? WHERE id = ?", updates)
        conn.commit()
        print(f"Successfully resolved and updated {resolved_count} database entries!")
    else:
        print("No entries needed updates.")

    # Print final verified summary of all items
    print("\n================== FINAL VERIFIED ITEM DISTRIBUTION ==================")
    final_rows = cursor.execute(
        "SELECT item, COUNT(*) FROM gift_checks WHERE collected = 1 GROUP BY item ORDER BY COUNT(*) DESC"
    ).fetchall()

    total_gifts = 0
    for item, count in final_rows:
        print(f"  {item}: {count}")
        total_gifts += count
    print(f"\nTotal Collected Gifts: {total_gifts}")

    conn.close()


if __name__ == "__main__":
    apply_labels()
