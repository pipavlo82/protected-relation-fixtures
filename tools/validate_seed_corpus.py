import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "v0" / "manifest.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    manifest = load_json(MANIFEST)
    assert manifest["schema"] == "protected-relation-corpus-manifest.v0"
    assert manifest["corpus_version"] == "v0"
    assert len(manifest["cases"]) == 5
    oracle_path = MANIFEST.parent / manifest["oracle"]["path"]
    oracle = load_json(oracle_path)
    case_ids = {Path(row["path"]).stem for row in manifest["cases"]}
    oracle_ids = set(oracle["results"].keys())
    assert case_ids == oracle_ids, f"oracle coverage mismatch: {case_ids ^ oracle_ids}"
    print("seed corpus validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
