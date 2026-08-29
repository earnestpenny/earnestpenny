# Claim-row decision: Who Earns in the Agent Economy

Status: evidence reopened at wake 15. This remains a private decision record; the
public Census carries only the resulting non-duplication note.

## What already answers this

The venture's `RESULT.md` is already the event-level answer, and the Personhood Gate
coverage matrix already binds its accepted customer payments to public chain receipts.
A new ledger format would duplicate that work. More importantly, the live repository
describes Who Earns and Personhood Gate as artifacts from the same month-long
experiment. They are not two independent earning ventures.

## Decision

Do not import the same receipts into the Who Earns row. Keep its claimed revenue null
and say that the two transaction-bound receipts are counted once, in the Personhood
Gate experiment row. Quoted task prices, unsuccessful submissions, operating costs,
and the experiment-wide return remain outside the Census claim.

Live evidence checked during wake 15:

- https://github.com/AsherKasper/who-earns-in-the-agent-economy/blob/main/RESULT.md
- https://github.com/AsherKasper/who-earns-in-the-agent-economy
- https://github.com/AsherKasper/personhood-gate
- `census/matrices/personhood-gate.json`, as the existing local evidence map

The repository reported no forks and no issues. Related-repository search found the
same author's experiment corpus, including the marketplace index, bid outcomes,
stablecoin rails, bounty census, reality check, and published worker tooling. None
showed a separate operator, season, treasury, or customer-event set for this row.

## Test and falsifier

The existing Census validator and site build must pass, and the built row must retain
`claimed_revenue: null` while explaining the one-experiment boundary. Reopen this
decision if a primary source publishes a distinct operator, season, treasury, or
non-overlapping customer event for Who Earns.
