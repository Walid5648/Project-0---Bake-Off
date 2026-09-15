# Label provenance and review

`items.jsonl` contains 10 development and 50 test items authored for this project's
synthetic retail schema. `src/dataset.py` is the initial catalog authoring source;
the JSONL file is the canonical reviewable dataset used by the benchmark.

All items currently have `review_status: draft_unreviewed` and no reviewers. Automated
checks execute each reference on three fixtures, check its result shape and require
a nonempty result on at least one fixture. These checks do not replace the assignment's
requirement for two people to check each label.

Use `python -m src.review --split test` to browse the catalog, and
`python -m src.review --id test_26 --fixture retail_a` to inspect a question, its gold
SQL and expected rows. Change the fixture to inspect the other data versions.

For each item, two actual reviewers should independently check:

1. Wording and business rules determine one unambiguous result table.
2. Reference SQL uses the correct status, dates, joins, aggregation level and money definition.
3. Requested columns, NULL behavior, duplicate handling and tie-breakers are correct.
4. Manually checked records or independent SQL support the expected answer on edge cases.

Record the two names in `reviewers` and use `review_status: reviewed` only after the
review is complete. Keep review corrections in version control. Freeze the test set
after the development pilot and before viewing final test model outputs. Retain failed
items; do not improve test wording selectively after seeing a particular model fail.
