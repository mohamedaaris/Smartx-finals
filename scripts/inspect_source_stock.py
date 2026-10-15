"""Count source cartons from the Blender export's component mesh bounds."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web/assets/source_objects.json"
ROW_BOUNDS = [(1, -2.56, 3.65), (2, -14.73, -8.52),
              (3, -27.07, -20.87), (4, -39.96, -33.76)]
COL_BOUNDS = [("A", -14.48, -9.79), ("B", -6.99, -2.30), ("C", .48, 5.17)]


def source_cartons(path=SOURCE):
    groups = defaultdict(list)
    for name, x0, y0, z0, x1, y1, z1 in json.loads(Path(path).read_text(encoding="utf-8")):
        if not name.lower().startswith("box") or max(x1 - x0, y1 - y0, z1 - z0) >= 3:
            continue
        match = re.match(r"(?i)^(box\d{3}|box\d{6}|box\d{2}|box)_", name)
        if not match:
            continue
        suffix = name.rsplit(".", 1)[1] if re.search(r"\.\d{3}$", name) else ""
        groups[(match.group(1).lower(), suffix)].append((x0, y0, z0, x1, y1, z1))
    cartons = []
    for group, meshes in groups.items():
        x0, y0, z0 = (min(mesh[i] for mesh in meshes) for i in range(3))
        x1, y1, z1 = (max(mesh[i + 3] for mesh in meshes) for i in range(3))
        if max(x1 - x0, y1 - y0, z1 - z0) >= 3:
            continue
        x, y = (x0 + x1) / 2, (y0 + y1) / 2
        shelf = next((f"{col}R{row}" for col, xa, xb in COL_BOUNDS
                      for row, ya, yb in ROW_BOUNDS if xa <= x <= xb and ya <= y <= yb), None)
        cartons.append({"source_id": f"{group[0]}{'.' + group[1] if group[1] else ''}",
                        "shelf": shelf, "position": [round((x0 + x1) / 2, 3),
                                                     round((y0 + y1) / 2, 3),
                                                     round((z0 + z1) / 2, 3)],
                        "bounds": [x0, y0, z0, x1, y1, z1], "mesh_parts": len(meshes)})
    return cartons


if __name__ == "__main__":
    cartons = source_cartons()
    print(f"Source cartons: {len(cartons)}")
    print("By shelf:", dict(sorted(Counter(c["shelf"] for c in cartons).items(), key=lambda kv: str(kv[0]))))
    print("Mesh parts per carton:", dict(Counter(c["mesh_parts"] for c in cartons)))
