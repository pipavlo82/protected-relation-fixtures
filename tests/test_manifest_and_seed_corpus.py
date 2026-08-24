import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "v0" / "manifest.json"


def test_manifest_shape_and_case_count() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema"] == "protected-relation-corpus-manifest.v0"
    assert manifest["corpus_version"] == "v0"
    assert len(manifest["cases"]) == 5


def test_seed_oracle_covers_all_cases() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    oracle_path = MANIFEST.parent / manifest["oracle"]["path"]
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    case_ids = {Path(row["path"]).stem for row in manifest["cases"]}
    oracle_ids = set(oracle["results"].keys())
    assert case_ids == oracle_ids
