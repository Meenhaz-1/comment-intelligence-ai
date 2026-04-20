import json

INPUT_PATH = "outputs/editorial_intelligence.jsonl"

recipe_ids = {
"669a6694ce501f7231beb7a9",
"64d2125f023ad8b411207094",
"633733d308196e4ac70304f1",
"633733d3e99f87106de7596e",
"667a262de4847a8af2d6dad1",
"62b0899bac7836cae7938d42",
"5f5bf02f74a2952305b7143d",
"63fcc897cd25bfbd2dccfab7",
"668cfc1c8badd0967e20d2c3",
"5d9c908242d7720008c1c744",
"57ad510753e63daf11a4dde8",
"5c0aa79c9d1454578ac78d74",
"5d1613e5e6a24100088d7283",
"5fd826ecca8baad6e2e91c47",
"601da76971887c3d6874b946",
"615b6635a35eadf8f1885e0a",
"5bdc8abfec66ce3784f6d0f8",
"60d37f01e8d6e66560c1f3bc",
"618938c2b2092ce829a0583f",
"5c48916c08898e65fa7a9a09",
"5bd1e99e52465b744a687956",
"5b2946e16544b36dce1fa581",
"5f7b83048c4d4eb3404401be",
"5eb5aebe26820561583377db",
"5f29d2e6669b6d39567d22b9",
"6346fc72ea436ec1472a365a",
"6101c8fccd46941e5e04efab",
"6011d813299209e33e329f54",
"5df94620693dc500084f7806",
"5f5fde7708c362986c6eeb44",
"5fb29693c76bf9c55fa65012",
"60426bf3051c297ccfc147b9",
"5d6fdc22f454300008b716bf",
"5f8c59c6dda393d6f500ff70",
"5e66873d0b469700088be66f",
"5d4d8b122c815a00080f976e",
"5e30aa8d6cf8d000080c3f92",
"5e74f83244b38d00086266b7",
"6142140d45a5ac104bd93750",
"65afc4cb0dffc342f518abc6",
"65804befee578673f186fe3e",
"62210b75283b313f9cf22fc7",
"618938c2b2092ce829a05841",
"5e459c799066ff0008317a56",
"5a9ec080fc24be1b59dc4182",
"5e908dabc5fc6300085dc143",
"5cbf2944926b39032807353c",
"5ad4fe5c541e7923b0bf6297",
"5bbe2e41801f710b477b692d",
"5cb61b95e23c841163a7ac21"
}

results = []

with open(INPUT_PATH, "r") as f:
    for line in f:
        row = json.loads(line)
        rid = row.get("recipe_id")

        if rid in recipe_ids:
            url = row.get("metadata", {}).get("url")
            results.append((rid, url))

# Print results
for rid, url in results:
    print(f"{rid} → {url}")

# Optional: save to CSV
import csv
with open("outputs/recipe_urls.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["recipe_id", "url"])
    writer.writerows(results)