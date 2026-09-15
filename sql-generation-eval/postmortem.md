# Development postmortem (draft)

This records actual issues encountered during implementation. It will be revised
after the frozen model runs; no model performance conclusions have been drawn yet.

## What went wrong

1. **The initial read-only authorizer rejected COUNT(*) queries.** SQLite reported a
   read with an empty column name and an unspecified database name for this operation.
   Requiring `database == main` rejected a valid aggregate. The authorizer now permits
   these reads only for the explicit benchmark table allowlist, while attachments,
   writes and schema metadata remain rejected. Tests cover allowed reads and denials.
2. **One draft question had an empty answer on every fixture.** The universal supplier
   coverage query required a supplier covering every active product in a category,
   but random data guaranteed no qualifying supplier. Added a complete supplier and
   a supplier missing one product so both correct and plausible incorrect answers can
   be distinguished. Validation now rejects questions empty on all three fixtures.
3. **Correlated seed rules limited return complexity.** Assigning returns to order IDs
   divisible by four coincided with the one-line-order generation rule. Changed the
   return schedule so both single-line and multi-line orders can contain returns.
4. **Local runtime installation hit network problems.** The package-manager installer
   download timed out. A direct download worked after handling an unavailable
   certificate-revocation endpoint, but transferred too slowly to complete in its
   download window. Runtime installation and actual model runs remain pending.

## What we learned

Reproducibility is not enough: deterministic data can repeatedly omit the very edge
case a question is meant to test. Inspect relationships and expected result shapes,
and test plausible wrong SQL as well as successful reference execution. Independent
human review of question meaning is still required; executing the gold SQL does not
prove that it expresses the intended business rule.

## Still to verify

Two human reviews per item, real local model behavior, common context/output limits,
7B GPU/CPU residency, error examples, latency distributions and cost assumptions.
