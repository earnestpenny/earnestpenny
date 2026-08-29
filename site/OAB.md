# Publish the claim. Bind the proof.

Open Agent Books is a public JSON disclosure for autonomous ventures. It gives a
reader one predictable place to find the venture, its treasuries, its monetary
events, its authorship record, and its corrections.

Open Agent Books does not run your wallet. It does not replace accounting software.
It does not decide whether a business is good. It makes each money claim small enough
to check.

## Why another format

[AgenticBooks](https://github.com/AgenticBooks/agenticbooks-mcp) gives an authenticated
agent access to private operating books. [Pinch](https://github.com/thecraighewitt/pinch)
keeps wallet policy and transaction history beside an agent. [Accounting Ops
Community](https://github.com/Unicorn-Commander/accounting-ops-community) provides a
full self-hosted ledger with reconciliation and reports.

Those tools do useful work at different layers. Open Agent Books is the small public
handoff they do not try to be. A venture can publish it beside any wallet or accounting
system without replacing that system.

## What the document says

- Who operates the venture, when it started, and which models authored its record.
- Which treasuries the venture discloses.
- Each monetary event's amount, asset, direction, source, destination, claimed
  category, and evidence.
- Whether that event is chain verified, bound to a receipt, attested by the operator,
  unclassified, or conflicted.
- Which corrections were appended to the record.

A chain can prove that a transfer happened. It cannot, by itself, prove that the
transfer was customer revenue. Open Agent Books keeps the transfer and the business
claim separate so a verifier can test both.

## Coverage without a grade

The core field list is fixed and ordered. A publisher cannot improve coverage by
leaving an inconvenient field out of the denominator. Evidence status belongs to one
field or one event, never to the venture as a whole. Payment cannot improve a result.

The Census can map public evidence from ventures that do not yet publish Open Agent
Books. The matrix shows what the source proves, what the operator merely says, and
what remains unknown.

## Adopt it

1. [Get the schema](oab-0.1.schema.json).
2. Publish a `books.json` file at the root of your site.
3. Bind every monetary event to a receipt, transaction, invoice, statement, or hash.
4. Keep corrections in the file. Add them. Do not erase them.

## Validate your books

The reference validator is deterministic. It accepts the schema and evidence fields,
or it names the field that failed. Conformance is free. It is also revocable when a
fresh check fails.

The standard is deliberately small. If a stranger can fetch the file, follow the
proof, and reproduce the claim, it is doing its job.
