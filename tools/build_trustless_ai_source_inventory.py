from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "evidence" / "external-systems" / "trustless-ai" / "v0"
REPOSITORIES = {
    "agent-contracts-examples": {
        "default_branch": "main",
        "commit": "60855b200745d2f6dfd24b266f95ca92ce102ed2",
        "tree": "9fe8df13e3194501ef49eac5fe94dbe8cb47a11b",
    },
    "agent-ercs": {
        "default_branch": "main",
        "commit": "01283ca57305f915afb560d23359a27fd748eb5a",
        "tree": "89d9d25f99b926e944f37920103191893a563a5b",
    },
    "ccip-router": {
        "default_branch": "main",
        "commit": "6bd66611b88a4751a0acc233c718aa9a13294de4",
        "tree": "22ca5dc999600e223b0625f3eaa4c1f44ab29aa3",
    },
    "primitives": {
        "default_branch": "main",
        "commit": "6b39e9540d4bd0a78decb588c0a8e328c303f208",
        "tree": "d1821bf1547632d531233007195241002b5459ee",
    },
    "recompute-kit": {
        "default_branch": "main",
        "commit": "d21bcc718bf505b46c4d32d7f3c858dff9d3e8bc",
        "tree": "ec51253674f7c145c4dfacc6fb58d3db9442a4a2",
    },
    "trustless-agent-substrate": {
        "default_branch": "feature/tas-poc",
        "commit": "a344ef80f7c52c03b9183814d1874b8054639c3e",
        "tree": "f3455e200fb4edc93452ff988832631058dfad3a",
    },
    "verify-layer": {
        "default_branch": "main",
        "commit": "84afc4b738dc37269089c858404eed8086435f5d",
        "tree": "d6b8e0022938f2197d7f54a68f3dff04ff689343",
    },
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw: bytes) -> str:
    completed = subprocess.run(
        ["git", "hash-object", "--stdin"], input=raw, capture_output=True, check=True,
    )
    return completed.stdout.decode("ascii").strip()


def upstream_blob(repo: str, commit: str, path: str) -> tuple[str, int]:
    completed = subprocess.run(
        ["gh", "api", f"repos/trustless-ai/{repo}/contents/{path}?ref={commit}"],
        capture_output=True,
        check=True,
    )
    value = json.loads(completed.stdout)
    if value.get("type") != "file":
        raise RuntimeError(f"upstream source is not a file: {repo}/{path}")
    return value["sha"], value["size"]


def live_metadata(name: str) -> dict[str, Any]:
    if name.startswith("gateway-verify."):
        return {
            "source_uri": "https://gateway.verticecriativo.pt/agent/verify/0x096e9df2fccbaf49525a22d3537670ec83746157846f0c25509a6483fe1d0a91",
            "surface": "public_no_auth_verify_endpoint",
        }
    endpoint = "https://ethereum-rpc.publicnode.com" if name.startswith("ethereum-") else "https://sepolia.base.org"
    result: dict[str, Any] = {
        "source_uri": endpoint,
        "surface": "direct_json_rpc",
        "chain_id": "1" if name.startswith("ethereum-") else "84532",
    }
    if name.startswith("ethereum-") and "code" in name:
        result["block"] = "0x18b42c0"
    if name.startswith("base-sepolia-") and "code" in name:
        result["block"] = "0x2c3a9cd"
    if name.startswith("base-sepolia-attestation-"):
        result["block"] = "0x2c26737"
        result["transaction"] = "0x458cf8a3b8f39c032dcec9eb2bf2932b7ca9be41662e35e4fbc21d0ea9eab381"
    return result


def main() -> int:
    records: list[dict[str, Any]] = []
    sources = LANE / "sources"
    for path in sorted(item for item in sources.rglob("*") if item.is_file()):
        relative_source = path.relative_to(sources).as_posix()
        repo, upstream_path = relative_source.split("/", 1)
        identity = REPOSITORIES[repo]
        raw = path.read_bytes()
        computed_blob = git_blob(raw)
        declared_blob, declared_size = upstream_blob(repo, identity["commit"], upstream_path)
        if computed_blob != declared_blob or len(raw) != declared_size:
            raise RuntimeError(f"captured source mismatch: {relative_source}")
        records.append({
            "relative_path": f"sources/{relative_source}",
            "classification": "SOURCE_GIT_BLOB",
            "source_uri": f"https://github.com/trustless-ai/{repo}/blob/{identity['commit']}/{upstream_path}",
            "repository": f"trustless-ai/{repo}",
            "default_branch": identity["default_branch"],
            "commit": identity["commit"],
            "tree": identity["tree"],
            "upstream_path": upstream_path,
            "git_blob_sha1": declared_blob,
            "byte_length": len(raw),
            "sha256": digest(raw),
        })
    live = LANE / "live"
    for path in sorted(item for item in live.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(LANE).as_posix()
        suffix = path.name.rsplit(".", 1)[-1]
        classification = "LIVE_REQUEST" if ".request." in path.name else "LIVE_HTTP_HEADERS" if suffix == "txt" and "headers" in path.name else "LIVE_RESPONSE"
        records.append({
            "relative_path": relative,
            "classification": classification,
            **live_metadata(path.name),
            "git_blob_sha1": None,
            "byte_length": len(raw),
            "sha256": digest(raw),
        })
    records.sort(key=lambda item: item["relative_path"])
    if len({item["relative_path"] for item in records}) != len(records):
        raise RuntimeError("duplicate inventory path")
    inventory = {
        "schema": "prf-trustless-ai-source-inventory.v0",
        "repositories": REPOSITORIES,
        "artifact_count": len(records),
        "total_bytes": sum(item["byte_length"] for item in records),
        "artifacts": records,
    }
    output = LANE / "source-inventory.json"
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"source inventory: PASS ({inventory['artifact_count']} files; {inventory['total_bytes']} bytes; sha256={digest(output.read_bytes())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
