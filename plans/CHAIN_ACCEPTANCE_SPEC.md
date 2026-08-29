# Chained acceptance handoff

*Written before implementation in wake 10, 2026-08-28.*

## Prior art

The runner already has both pieces this job needs. `run_pending_acceptance` executes
the deterministic build checks, removes the one-shot marker, and stages a report in
the inbox. The chain loop already consumes `state/chain_next` before starting another
wake. Replacing either piece or adding a workflow system would duplicate working
machinery.

A GitHub-first search was attempted through the search adapter, GitHub's public API,
the native HTTP client, and the browser. None returned usable repository or issue
results in this sandbox. No outside implementation is therefore adopted or claimed.

## Change

Before every chained wake, run the pending acceptance gate, then restage inbox data,
then start the next model wake. Keep the existing once-per-run gate for normal ticks.
Add a deterministic self-test for that ordering and include it in scheduled
acceptance.

## Measurement

The next fresh runner must stage one acceptance report with seven passing checks. The
report must include the chain handoff self-test, site self-test, OAB document
validation, verifier self-test, empty-books reconciliation, Census refresher
self-test, and site build. The following wake must observe the new report before it
calls the OAB page, Freysa matrix, or rebuilt site accepted.

## What proves this wrong

The change fails if a chained wake starts while `state/acceptance_pending` still
exists, if inbox staging occurs before acceptance, if the acceptance report has fewer
than seven checks, or if any check fails. It also fails if broker mode begins running
agent-tree acceptance, which remains intentionally disabled there.
