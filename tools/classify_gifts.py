"""
tools/classify_gifts.py

Uses image clustering to identify Lizard Doggo gifts that failed OCR (recorded as None).
Groups slot images by pixel similarity and propagates successfully OCR'd item labels
to all None entries of the same item.
"""

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def classify_gifts():
    db_path = Path("stats") / "gift_history.db"
    if not db_path.exists():
        print(f"Error: Database not found at {db_path.absolute()}")
        return

    print(f"Connecting to database: {db_path.absolute()}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all collected gifts
    rows = cursor.execute(
        "SELECT id, ts, doggo, item, crop_path FROM gift_checks WHERE collected = 1"
    ).fetchall()

    print(f"Found {len(rows)} collected gifts in database.")

    # Load images and group them
    records = []
    loaded_images = []

    for row_id, ts, doggo, item, crop_path in rows:
        if not crop_path:
            continue

        img_path = Path(crop_path)
        if not img_path.exists():
            # Try relative to project root
            img_path = project_root / crop_path
            if not img_path.exists():
                continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        records.append({
            "id": row_id,
            "ts": ts,
            "doggo": doggo,
            "item": item if (item and item.lower() != "none") else None,
            "crop_path": crop_path
        })
        loaded_images.append(img)

    print(f"Successfully loaded {len(loaded_images)} slot icon images for clustering.")

    # Cluster images using Mean Absolute Difference (MAD)
    # If MAD < 8.0, they represent the exact same item
    threshold = 8.0
    clusters = []  # List of dicts: {"rep": image, "records": [record_dict, ...]}

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
            clusters.append({
                "rep": img,
                "records": [rec]
            })

    print(f"Grouped images into {len(clusters)} unique item clusters.")

    # Process and propagate labels
    resolved_count = 0
    updates = []

    for c_idx, cluster in enumerate(clusters):
        recs = cluster["records"]
        # Find all non-None names in this cluster
        names = [r["item"] for r in recs if r["item"] is not None]

        if not names:
            # Entire cluster has no OCR labels
            rep_rec = recs[0]
            print(f"  Cluster {c_idx}: {len(recs)} items - UNLABELED (e.g. {rep_rec['crop_path']})")
            continue

        # Choose the most common name in the cluster as the resolved label
        most_common = Counter(names).most_common(1)[0][0]

        # Check how many None entries in this cluster we can resolve
        nones_in_cluster = sum(1 for r in recs if r["item"] is None)

        if nones_in_cluster > 0:
            print(f"  Cluster {c_idx}: Resolving {nones_in_cluster} 'None' entries to '{most_common}' (based on {len(names)} OCR hits)")
            for r in recs:
                if r["item"] is None:
                    updates.append((most_common, r["id"]))
                    resolved_count += 1

    # Execute database updates
    if updates:
        print(f"\nApplying {len(updates)} database updates...")
        cursor.executemany(
            "UPDATE gift_checks SET item = ? WHERE id = ?",
            updates
        )
        conn.commit()
        print("Database updates successfully committed.")
    else:
        print("\nNo entries needed resolving.")

    # Print final summary of all items
    print("\n================== Updated Item Distribution ==================")
    final_rows = cursor.execute(
        "SELECT item, COUNT(*) FROM gift_checks WHERE collected = 1 GROUP BY item ORDER BY COUNT(*) DESC"
    ).fetchall()

    for item, count in final_rows:
        print(f"  {item}: {count}")

    conn.close()


if __name__ == "__main__":
    classify_gifts()
