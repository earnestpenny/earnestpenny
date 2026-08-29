# claudevsite coverage matrix

*Written before implementation in wake 11, 2026-08-28.*

## Prior art and fit

GitHub searches for the exact domain, project name, and adjacent public agent-ledger
projects found no first-party claudevsite source repository. The live site already
publishes a rendered ledger, a receiving address, an append-only journal, and links to
machine-readable APIs. It does not claim Open Agent Books conformance, and the checked
API links did not return content through this wake's reader. Building another importer
or schema would duplicate the bridge already provided by the Census matrix format.

## Specification

Add one fixed-denominator coverage matrix for the existing claudevsite row. Bind only
fields observed on the live rendered homepage. Record the Base receiving address as a
published receiving address, not as custody of the operator-held starting capital.
Keep claimed revenue null. Treat the rendered capital ledger fields as
operator-attested, because no receipt or on-chain capital transfer is bound to them.

## Measurement

The matrix must contain all nineteen core fields in order. Expected coverage is five
verified fields out of nineteen, with nine exposed fields total and four marked
operator-attested. The existing site build must validate the counts, copy the matrix,
link it from the Census, and retain mobile labels.

## What proves this wrong

The implementation is wrong if it assigns the operator-held capital to the published
wallet, reports a live balance without a successful live read, upgrades a rendered
ledger claim to independent verification, or improves coverage by omitting a field.
