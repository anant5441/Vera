"""Generate canonical 30-line submission.jsonl for evaluation."""

import json
from pathlib import Path
from bot import compose

DATASET_DIR = Path("magicpin-ai-challenge/expanded")
OUTPUT_FILE = Path("submission.jsonl")


def main():
    pairs_file = DATASET_DIR / "test_pairs.json"
    pairs = json.loads(pairs_file.read_text(encoding="utf-8"))["pairs"]
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for pair in pairs:
            test_id = pair["test_id"]
            tid = pair["trigger_id"]
            mid = pair["merchant_id"]
            cid = pair["customer_id"]

            trg = json.loads((DATASET_DIR / "triggers" / f"{tid}.json").read_text(encoding="utf-8"))
            m = json.loads((DATASET_DIR / "merchants" / f"{mid}.json").read_text(encoding="utf-8"))
            c = (
                json.loads((DATASET_DIR / "customers" / f"{cid}.json").read_text(encoding="utf-8"))
                if cid
                else None
            )
            cat_slug = m.get("category_slug", "restaurants")
            cat = json.loads((DATASET_DIR / "categories" / f"{cat_slug}.json").read_text(encoding="utf-8"))

            res = compose(cat, m, trg, c)
            entry = {
                "test_id": test_id,
                "body": res["body"],
                "cta": res["cta"],
                "send_as": res["send_as"],
                "suppression_key": res["suppression_key"],
                "rationale": res["rationale"],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Generated {len(pairs)} submission entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
