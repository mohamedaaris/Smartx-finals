"""Check the exported asset's actual provenance and original robot identities."""
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SuppliedModelValidation(unittest.TestCase):
    def test_original_model_and_export_identity(self):
        asset = ROOT / "web/assets/warehouse.glb"
        manifest = json.loads((asset.parent / "model_manifest.json").read_text())
        self.assertEqual(Path(manifest["source"]).name, "warehouse1.blend")
        self.assertTrue(Path(manifest["source"]).exists())
        with asset.open("rb") as stream:
            magic,version,length = struct.unpack("<III",stream.read(12))
            size,kind = struct.unpack("<II",stream.read(8))
            gltf = json.loads(stream.read(size))
        self.assertEqual(magic,0x46546C67)
        self.assertEqual(version,2)
        self.assertEqual(length,asset.stat().st_size)
        names = {node.get("name") for node in gltf["nodes"]}
        self.assertIn("AMR_ORIGINAL_WAREHOUSE",names)
        self.assertEqual(len(manifest["robots"]),5)
        for robot in manifest["robots"].values():
            self.assertIn(robot["node"],names)
            self.assertTrue(robot["source_object"].startswith("robot"))
        self.assertEqual(len(manifest["slots"]),24)
        self.assertTrue(all("particle board" in slot["source_board"] for slot in manifest["slots"].values()))


if __name__ == "__main__":
    unittest.main()
