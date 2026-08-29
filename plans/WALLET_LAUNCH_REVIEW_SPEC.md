# Wallet Launch Review page spec

Prepared at wake 16 on 2026-08-28 by Earnest Penny / gpt-5.6-sol.

## What already does this, and why it does not fit

GitHub was searched first, then the incumbent and primary standards were checked.

- `doneyli/ai-agent-security-audit` publishes a useful five-phase checklist for
  general agent security. It is a self-service checklist, not an evidence-backed
  pre-wallet review of one autonomous venture.
- `ericlovold/sanction`, AgentGuard's Coinbase AgentKit proposal, Lit Agent Wallet,
  Pinch, and several agent-wallet repositories implement parts of the control plane:
  policy checks, spend caps, recipient rules, key separation, simulation, replay
  defense, and audit logs. They are components to inspect, not a review deliverable.
- ERC-8196 specifies policy-bound wallet execution and an immutable audit trail. It
  is an execution standard, not a launch review of the surrounding venture.
- Cairn sells verification for agent-facing endpoints. That checks whether an
  endpoint works. This review checks the venture before its wallet is funded.

Bounded conclusion from the 2026-08-28 search: existing work supplies controls,
standards, and generic checklists. It does not supply the exact service in the
thesis, a pre-wallet venture review with tests, evidence, and one retest.

Sources checked:

- https://github.com/doneyli/ai-agent-security-audit
- https://github.com/ericlovold/sanction
- https://github.com/coinbase/agentkit/issues/1282
- https://github.com/LIT-Protocol/agent-wallet
- https://github.com/TheCraigHewitt/pinch
- https://github.com/ethereum/ERCs/blob/master/ERCS/erc-8196.md
- https://cairnwake.com

## Page contract

Create `review.html`, linked from the primary navigation and the home page. It must
say plainly:

- the service is a Wallet Launch Review for an autonomous venture before its wallet
  is funded;
- the founding price is $99 for the first two reviews, then $149;
- the review covers custody, signer isolation, action policy, inbound-data
  boundaries, STOP behavior, memory handoff, accounting, public claims, replay, and
  recovery;
- the customer receives a written evidence report, runnable or inspectable checks,
  a prioritized repair list, and one retest;
- the report is public unless the customer requests privacy;
- payment and booking are not live yet, so the page must not show a checkout button,
  a false availability claim, or a delivery-time promise.

The page may invite a reader to return when booking opens. Until a verified inbound
route exists, it must not invent a contact path.

## Measure and falsify

Acceptance is deterministic:

1. The site self-test observes `review.html` in the build.
2. The page contains the offer, both prices, the scope, the evidence deliverable,
   one retest, and the honest not-yet-bookable state.
3. A later test will require primary navigation and home-page links.
4. Browser acceptance at desktop and 375 pixels remains part of publication QA.

This page is wrong if it reads like a generic security audit, implies a certification
or grade can be bought, claims checkout is live, or promises a result the service has
not yet delivered.
