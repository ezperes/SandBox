import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.contracts import CANONICAL_CONTRACTS

OUT = ROOT / "harness" / "schemas"
OUT.mkdir(parents=True, exist_ok=True)
bundle = {}
for contract in CANONICAL_CONTRACTS:
    schema = contract.model_json_schema()
    bundle[contract.__name__] = schema
    (OUT / f"{contract.__name__}.schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "all.schemas.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"exported {len(CANONICAL_CONTRACTS)} schemas to {OUT}")
