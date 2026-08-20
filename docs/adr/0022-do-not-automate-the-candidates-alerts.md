# 0022. Do not automate the candidate's alerts

**Status:** Accepted
**Date:** 2026-08-19

Builds on [0021](0021-alert-on-signals-the-host-cannot-drop.md), which made the
alert conditions trustworthy enough to be worth routing anywhere.

This record was drafted deciding the opposite — a plain-language notification
path to Julia on activate, acknowledge and close. It was built, tested against
the live account, and abandoned. What follows is the reasoning that survived
contact, because the negative result is the useful part.

## Context

Every alerting decision so far has had one reader: the person who can fix the
thing. Julia is the candidate. She cannot fix the API, has no New Relic account,
and during a campaign is the person most likely to be asked "is your website
broken?" by somebody standing in front of her.

That is a real information need. She wants to know that supporters are being
turned away, that somebody is dealing with it, and when it is over. She does not
want — and is actively harmed by — a condition name, an issue URL, a NRQL
snippet, or an alert about a defence working correctly.

The plan was three emails per incident in plain language, filtered to the two
conditions that mean supporters cannot submit a form.

## What building it established

### New Relic will not let a workflow fire on one issue state

`notificationTriggers` **must contain `ACTIVATED`**:

```
destinationConfigurations[0].notificationTriggers: Must contain ACTIVATED
```

So "one workflow per state, each with fixed prose" is not expressible. A channel
also belongs to exactly one workflow (`Channels ids are already in use by
workflows [...]`), so the objects cannot be shared either. Varying wording by
state requires one workflow with all three triggers and a template branching on
`{{state}}`. That much is workable — the handlebars forms were verified against
the account, and `{{#if (eq state 'X')}}` with nested `{{else}}` renders.

### The email itself is not ours to write

This is the one that ended it. The EMAIL channel type exposes exactly two
fields, and the schema is explicit about what the second one is:

| key                  | label                                          |
| -------------------- | ---------------------------------------------- |
| `subject`            | Email subject                                  |
| `customDetailsEmail` | **Additional** information to put in the email |

Everything else is New Relic's. A delivered notification leads with a priority
badge and the raw issue title, then a **Go to issue** button into an account she
does not have, then alert-event counts, impacted entity names, and a table
giving the policy name, the condition name and the **NRQL query**. Our
plain-language paragraph is appended at the bottom under the heading "Custom
details".

The subject line is genuinely ours and reads well. Nothing below it does. The
design promised "no condition names, no issue URLs, no jargon" and the platform
cannot deliver any of the three.

### A relay would have to live outside our own infrastructure

Full control of the message means leaving New Relic as a webhook and having
something else send the mail. That something else **cannot be this API**. The
alert most worth sending is the one that fires when `/health/deep` fails, and
the most likely reason it fails is SMTP — so relaying the candidate's outage
notification through the mail path that is down is a guarantee of silence at the
one moment it matters.

An independent relay is buildable: Cloudflare already fronts these hostnames
([0019](0019-cloudflare-in-front.md)), and a Worker calling a transactional mail
API would be genuinely independent of the failing host. It is also a new
deployable with its own credential, its own drift surface, and its own outage
modes, standing between an alert and one reader, for one municipal race.

## Decision

**No automated notification reaches the candidate. The engineer is alerted, and
tells her.**

Both policies notify `dylan@voteforjulia.com` and nothing else. Julia's
destination, channel and workflow were created, verified, and deleted; her
address is not stored in New Relic.

The judgement is that a human relay is better here than either available
automation. An email she cannot read past the subject line teaches her to ignore
the channel — the precise failure the original design existed to prevent — and
a bespoke relay is disproportionate infrastructure to avoid sending a text
message.

## Consequences

- **The candidate's awareness now depends on the engineer being reachable.**
  That is the real cost and it should not be dressed up. There is a single
  maintainer, so in practice her old path depended on him anyway; this makes the
  dependency visible instead of implied.
- **Two alert policies remain, and their original justification is gone.** The
  split — `voteforjulia — API` and `voteforjulia — Campaign visible` — existed
  so a workflow could select Julia's conditions structurally rather than by an
  unvalidated condition-name predicate. With no workflow of hers to drive, it
  now only marks which alerts mean supporters are being turned away. That is
  still useful for triage, and it is what a relay would need if this is ever
  revisited, but **it is structure kept past its reason** and collapsing the two
  is a reasonable future change.
- **The engineer needs one workflow per policy**, because a channel cannot be
  shared. A third policy added later silently halves his coverage unless a
  workflow is added with it.
- **`violationTimeLimitSeconds` on both campaign-visible conditions stays at 30
  days.** It was raised because a force-closed issue sends an all-clear, which
  would have been a lie told to the candidate. The reason is weaker now that
  only the engineer reads it, but a false all-clear is still a false all-clear.
- **If this is revisited, the finding to start from is that the message must be
  built outside New Relic.** No amount of template work fixes an email whose
  body we only get to append to.
