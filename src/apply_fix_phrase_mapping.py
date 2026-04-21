#!/usr/bin/env python3

"""
Apply canonical fix mapping to all raw fix phrases.

Inputs:
- outputs/raw_fix_phrases_long.csv
- outputs/fix_phrase_mapping_template.csv

Output:
- outputs/raw_fix_phrases_mapped.csv
"""

from __future__ import annotations

import pandas as pd


RAW_PATH = "outputs/raw_fix_phrases_long.csv"
MAPPING_PATH = "outputs/fix_phrase_mapping_template_clean.csv"
OUTPUT_PATH = "outputs/raw_fix_phrases_mapped.csv"


def normalize_text(text: object) -> str:
    if pd.isna(text):
        return ""
    return " ".join(str(text).lower().strip().split())


def main() -> None:
    raw = pd.read_csv(RAW_PATH)
    mapping = pd.read_csv(MAPPING_PATH)
    
    print("MAPPING_PATH:", MAPPING_PATH)
    print(mapping.loc[:5, ["raw_fix_phrase", "canonical_fix", "fix_family", "keep_flag"]])

    required_raw_cols = ["raw_fix_phrase"]
    required_mapping_cols = ["raw_fix_phrase", "canonical_fix", "fix_family", "keep_flag"]

    missing_raw = [c for c in required_raw_cols if c not in raw.columns]
    missing_mapping = [c for c in required_mapping_cols if c not in mapping.columns]

    if missing_raw:
        raise ValueError(f"Missing columns in raw file: {missing_raw}")
    if missing_mapping:
        raise ValueError(f"Missing columns in mapping file: {missing_mapping}")

    # Normalize mapping columns
    mapping["raw_fix_phrase_norm"] = mapping["raw_fix_phrase"].map(normalize_text)
    mapping["canonical_fix"] = mapping["canonical_fix"].map(normalize_text)
    mapping["fix_family"] = mapping["fix_family"].map(normalize_text)
    mapping["keep_flag"] = mapping["keep_flag"].map(normalize_text)

    # Keep only rows explicitly marked keep and with non-empty canonical fields
    mapping_keep = mapping[
        (mapping["keep_flag"] == "keep")
        & (mapping["raw_fix_phrase_norm"] != "")
        & (mapping["canonical_fix"] != "")
        & (mapping["fix_family"] != "")
    ].copy()

    print(f"Total mapping rows: {len(mapping)}")
    print(f"Rows marked keep: {(mapping['keep_flag'] == 'keep').sum()}")
    print(f"Usable keep rows: {len(mapping_keep)}")

    # Remove duplicate phrase mappings, keep first
    mapping_keep = mapping_keep.drop_duplicates(subset=["raw_fix_phrase_norm"], keep="first")

    raw["raw_fix_phrase_norm"] = raw["raw_fix_phrase"].map(normalize_text)

    mapping_dict = {
        row["raw_fix_phrase_norm"]: (row["canonical_fix"], row["fix_family"])
        for _, row in mapping_keep.iterrows()
    }

    mapped = raw["raw_fix_phrase_norm"].apply(lambda x: mapping_dict.get(x, (None, None)))

    raw["canonical_fix"] = mapped.apply(lambda x: x[0])
    raw["fix_family"] = mapped.apply(lambda x: x[1])
    raw["is_mapped"] = raw["canonical_fix"].notna()

    raw.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved mapped output to {OUTPUT_PATH}")
    print(f"Total rows: {len(raw)}")
    print(f"Mapped rows: {raw['is_mapped'].sum()}")
    print(f"Unmapped rows: {(~raw['is_mapped']).sum()}")


if __name__ == "__main__":
    main()