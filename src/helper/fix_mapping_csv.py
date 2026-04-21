#!/usr/bin/env python3

"""
Fix malformed rows in fix_phrase_mapping_template.csv

Specifically:
- Rows with too many commas (11 fields instead of 10)
- Typical pattern: ",,,,drop," → should be ",,,drop,"

Also trims whitespace and rewrites a clean CSV.

Input:
outputs/fix_phrase_mapping_template.csv

Output:
outputs/fix_phrase_mapping_template_clean.csv
"""

import csv

INPUT_PATH = "outputs/fix_phrase_mapping_template.csv"
OUTPUT_PATH = "outputs/fix_phrase_mapping_template_clean.csv"

EXPECTED_COLS = 10


def fix_row(row):
    """
    Fix rows with too many columns.

    Strategy:
    - If row has 11+ columns, assume extra empty column before keep_flag
    - Remove one empty column before 'drop' or 'keep'
    """
    if len(row) == EXPECTED_COLS:
        return row

    # Try to fix rows with extra empty fields
    while len(row) > EXPECTED_COLS:
        # Find 'drop' or 'keep'
        for i, val in enumerate(row):
            if val.strip().lower() in ("drop", "keep", "maybe"):
                # Remove previous empty column if exists
                if i > 0 and row[i - 1].strip() == "":
                    del row[i - 1]
                    break
        else:
            # fallback: just remove second-last column
            del row[-2]

    return row


def main():
    fixed_rows = []

    with open(INPUT_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)

        for line_num, row in enumerate(reader, start=1):
            original_len = len(row)

            if original_len != EXPECTED_COLS:
                print(f"Fixing line {line_num}: {original_len} columns")

                row = fix_row(row)

                if len(row) != EXPECTED_COLS:
                    print(f"WARNING: still malformed at line {line_num} → {len(row)} columns")

            fixed_rows.append([cell.strip() for cell in row])

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(fixed_rows)

    print(f"\nClean file written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()