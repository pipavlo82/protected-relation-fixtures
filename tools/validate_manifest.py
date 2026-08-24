import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "v0" / "manifest.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    manifest = load_json(MANIFEST)
    assert manifest["schema"] == "protected-relation-corpus-manifest.v0"
    assert manifest["corpus_version"] == "v0"
    for row in manifest["cases"]:
        path = MANIFEST.parent / row["path"]
        assert path.exists(), f"missing case {row['path']}"
        assert sha256_file(path) == row["sha256"], f"digest mismatch for {row['path']}"
    oracle = manifest["oracle"]
    oracle_path = MANIFEST.parent / oracle["path"]
    assert oracle_path.exists(), "missing oracle"
    assert sha256_file(oracle_path) == oracle["sha256"], "oracle digest mismatch"
    print("manifest validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
