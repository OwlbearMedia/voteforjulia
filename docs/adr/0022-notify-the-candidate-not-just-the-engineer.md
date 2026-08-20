# 0022. Notify the candidate, not just the engineer

**Status:** Accepted
**Date:** 2026-08-19

Builds on [0021](0021-alert-on-signals-the-host-cannot-drop.md), which made the
alert conditions trustworthy enough to route to somebody who cannot evaluate
them.

## Context

Every alerting decision so far has had one reader: the person who can fix the
thing. Julia is the candidate. She cannot fix the API, has no New Relic account,
and during a campaign is the person most likely to be asked "is your website
broken?" by somebody standing in front of her.

That is a real information need and it is not the same as the engineer's. She
needs to know that supporters are being turned away, that somebody is dealing
with it, and when it is over. She does not need — and is actively harmed by — a
condition name, an issue URL, a NRQL snippet, or an alert about a defence
working correctly.

Three things make this harder than pointing a second email address at the
existing policy.

**An alert with no resolution is worse than no alert.** If she is told a problem
opened and never told it closed, the open state persists in her head
indefinitely. The lifecycle matters more than the opening notification: the
"fixed" email is the one that does the work.

**Precision is the wrong goal; a false positive is much more expensive here than
a slow true positive.** She cannot triage. Every alert she receives is either
acted on socially — a phone call, a worried volunteer — or teaches her to ignore
the channel. The condition that fired spuriously on 2026-08-17
([0021](0021-alert-on-signals-the-host-cannot-drop.md)) would have been her
first ever notification, about a site that was completely healthy.

**Not every alert on the policy concerns her.** A tripped rate limiter mostly
means a scanner found the forms and was refused, which is the system working.
"Your website is under attack" is true, useless, and frightening.

## Decision

**A separate notification path, filtered to the two conditions that mean
supporters are being turned away, sending fixed plain-language prose on three
issue states.**

### What reaches her

| Condition                           | Julia | Why                                             |
| ----------------------------------- | ----- | ----------------------------------------------- |
| API dependency check failing        | yes   | the forms genuinely cannot take submissions     |
| Rate limiter tripping — hourly tier | yes   | sustained refusals; real people may be affected |
| Rate limiter tripping — burst tier  | no    | a refused scanner is the defences working       |
| Synthetic monitor not running       | no    | means we cannot see, not that she is down       |
| API serving 5xx                     | no    | overlaps the dependency check; engineer's view  |

The hourly tier is included and the burst tier is not, and that split is the
whole design in miniature: both are "the rate limiter tripped", but only one of
them describes a caller patient enough to plausibly be a person.

Her hourly-tier condition is further narrowed to the two **form** endpoints.
`/health/deep` has its own 30/hour allowance and a scanner exhausting it says
nothing about whether a supporter can submit anything — but the email she would
receive says the forms may not be working. The filter that keeps the two apart
lives in the NRQL, so it is invisible from the workflow that sends the mail.

### One workflow and a branching template, because the platform forces it

This record originally decided the opposite: three workflows, one issue state
each, each with its own channel of fixed literal prose. The argument was that a
malformed handlebars expression does not fail loudly — it sends the template
source — and `{{#if state}}` in a candidate's inbox during an outage is worse
than the outage.

**That design is not possible.** Building it on 2026-08-19 turned up two
constraints, neither documented anywhere we had looked and neither visible in
the GraphQL schema:

- **`notificationTriggers` must contain `ACTIVATED`.** A workflow that fires
  only on acknowledgement or only on closure is rejected with
  `destinationConfigurations[0].notificationTriggers: Must contain ACTIVATED`.
  So one-state-per-workflow cannot be expressed at all.
- **A channel may belong to exactly one workflow.** Reusing one produces
  `Channels ids are already in use by workflows [...]`.

The first kills the design outright. Varying the wording by state therefore
requires exactly what was rejected: one workflow carrying all three triggers,
one channel, and a template that branches on `{{state}}`.

The original concern was legitimate and does not go away, so it is answered by
verification rather than by structure. Both conditional forms were confirmed
against the live account before anything was pointed at Julia — a probe channel
on the engineer's own address rendered `{{#if (eq state 'X')}}`, `{{#eq}}` and a
doubly-nested `{{else}}` correctly. **That probe is the mitigation. Any future
edit to her template repeats it against a non-candidate address first.**

One property of the template is load-bearing and is not obvious from reading it:
**only an explicit `CLOSED` produces the all-clear.** The branches are ordered
`CLOSED` → `ACTIVATED` → everything else, so an unexpected state falls through
to "Dylan is looking into it" rather than to "the website is working normally
again". Reversing that order would make a surprise state tell the candidate her
site is fixed when nobody has said so.

### Who sees what is structural, not a string match

Julia's workflow selects issues by **policy**, not by condition name. The two
conditions she should hear about live on their own policy,
`voteforjulia — Campaign visible`; everything else stays on
`voteforjulia — API`.

Filtering by condition name was the first design and is a trap.
`AiWorkflowsPredicateInput.attribute` is an unvalidated `String`, so a wrong
attribute — `conditionName` where the account wanted `accumulations.conditionName`,
say — is accepted, matches nothing, and leaves a workflow that reports healthy
and never fires. On the path to a non-technical stakeholder that is the worst
available failure, and it is invisible until the incident it was built for.

Two policies cost a second object to keep in step and buy a filter that cannot
silently miss. The predicate used, `labels.policyIds`, is the one shape already
proven working in this account.

### Wording

No condition names, no issue URLs, no numbers, no jargon. Each email says what
is happening in supporter terms, what is being done, and explicitly whether she
needs to act — which is almost always "no". The acknowledgement email exists
solely so the gap between "broken" and "fixed" is not silence.

## Consequences

- **The acknowledgement email depends on a human step.** It fires on the issue
  being acknowledged in New Relic, not on work starting. Fixing the problem
  without acknowledging sends her "it broke" and later "it is fixed" with
  nothing between, which reads as nobody having noticed for the duration. The
  runbook says acknowledge first, then fix. This is a process dependency
  introduced by a technical decision and it will eventually be forgotten.
- **A force-closed issue sends a false all-clear.** New Relic closes an issue
  when `violationTimeLimitSeconds` expires whether or not it recovered, and a
  close notification is a close notification. At the default 259200 that is an
  outage running 72 hours and Julia being told it is over. The hourly rate-limit
  condition is set to 2592000 for this reason. The trade-off is that a genuinely
  stuck issue stays open longer instead of resetting. **Both** of her conditions
  carry it — the dependency check as much as the rate limit — because the
  hazard belongs to the notification path, not to any one condition.
- **`PER_CONDITION` incident preference means she can receive two openings for
  one underlying fault.** Kept anyway — collapsing them would undo the reason
  the policy is `PER_CONDITION` in the first place.
- **Her whole path now hangs on one template.** The three-object design had the
  property that a broken piece cost one email; a single branching template that
  fails costs the entire lifecycle. Nothing about the platform lets us have the
  other arrangement, so the residual risk is real and is carried by the probe
  ritual above rather than removed.
- **The engineer needs his own workflow per policy.** Splitting the conditions
  across two policies means the engineer-facing coverage is two workflows and
  two channels, not one, because a channel cannot be shared. Adding a third
  policy later silently halves his coverage unless a workflow is added with it.
- **Julia's address is not in the repository.** It is public. The mutations
  carry a `<JULIA_EMAIL>` placeholder and the live value exists only in the New
  Relic UI, which makes the destination one more thing that drifts silently and
  cannot be rebuilt from the checkout alone.
- **She is now a reason not to let alerts be noisy.** Any future condition added
  to the policy has to make an explicit decision about her workflow, and a
  careless one is felt by the candidate rather than absorbed by the engineer.
