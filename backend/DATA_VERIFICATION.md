# Data Verification Policy

Every numeric field in this database (`rebate_percent`, `max_cap_amount`, `min_total_budget`, `min_qualifying_spend`, etc.) is stored **only** when taken from **official** sources:

- **`source_url`** — primary official page, PDF, or legal instrument
- **`source_description`** — specific section/article reference (e.g., "Art. 36.2 Ley 27/2014", "BFI Cultural Test Guidance, Section 3.2")
- **`notes`** — key conditions quoted or paraphrased from the source
- **`last_verified`** — date the source was last checked

## What is excluded

- Rows with **no** official citation for their numbers
- **Approximate**, **industry-summary**, or **illustrative** figures
- **Treaty minimum shares** unless the value appears in the linked treaty or official summary

## Adding data

1. Add or edit entries in `seed_data.py`
2. Fill **all four** provenance fields (`source_url`, `source_description`, `notes`, `last_verified`)
3. Run `python seed_data.py` to repopulate the database

## Disclaimer

Even verified figures change with **budgets, law amendments, and programme rounds**. This tool does **not** replace professional accounting or legal advice.
