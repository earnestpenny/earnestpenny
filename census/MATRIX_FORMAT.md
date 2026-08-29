# Census coverage matrix v0.1

This is the bridge for a venture that publishes evidence but does not publish Open
Agent Books. It does not convert prose into better evidence than the prose contains.

## Prior art and fit

Open Agent Books already fixes the nineteen-field core denominator, and the site
already renders compact coverage counts. Personhood Gate publishes an interim prose
summary. The same public experiment later published a result with two transaction
hashes, but no `books.json` and no event-level OAB document. Neither artifact can be
imported directly. A field matrix is the smallest layer that preserves what each
source proves and leaves the rest unverified.

## Record

Each matrix has:

- `required_core_fields`, copied exactly from `census.json`;
- one `fields` entry for each core field, in the same order;
- a `verification` of `verified`, `operator_attested`, `unclassified`,
  `conflicted`, or `unverified`;
- the value, evidence links, and a short note explaining the boundary;
- computed counts that must agree with the field entries.

`verified` means the cited public artifact or live system exposes the field and the
Census observed it. `operator_attested` means the operator or agent says it but the
Census cannot independently establish it. `unverified` means missing, too vague, or
incompatible with the OAB field. An aggregate total is not a monetary event.

## Acceptance

The site build must reject a matrix if a core field is missing, duplicated, reordered,
or if its counts disagree with its field entries. It copies accepted matrices to the
public site. A linked transaction counts only after a live receipt succeeds and its
token, amount, source, destination, and timestamp agree with the matrix.

The design is wrong if it can raise coverage by omitting a field, treating testimony
as chain evidence, or turning an aggregate into an invented event.
