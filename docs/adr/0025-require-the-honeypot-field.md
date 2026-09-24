# 0025. Require the honeypot field to be present, and keep the form-encoded path

**Status:** Accepted
**Date:** 2026-09-23

Amends [0016](0016-second-tier-rate-limiting-and-honeypot.md). 0016 refused a
submission whose `referralCode` was non-empty; this also refuses one where the
field is missing. What 0016 and
[0017](0017-origin-trust-boundary-and-health-probe-cache.md) decided about
keeping the form-encoded, no-JavaScript submission path is **unchanged**. This
record looks at that decision again and keeps it.

## Context

At 2026-09-06T00:35:19Z a spam submission reached the volunteer sheet and the
campaign inbox. It came from an AWS EC2 address that crawled seven pages in two
seconds and fetched no CSS or JS. It then posted form-encoded to `/send-email`
and got a `200`. Its field names included `helpWays[]`, the raw HTML input name.
The scripted path sends `helpWays` in JSON. So the bot scraped the rendered form
and posted the inputs it had values for. It never sent `referralCode`, so the
filled-field check had nothing to see. It sent two requests in total, so the
rate limiter could not engage either
([#175](https://github.com/OwlbearMedia/voteforjulia/issues/175) has the full
reconstruction).

This is the second recorded case with the same gap. 0016 notes that the
2026-08-10 operator, retested on 2026-08-14, posted a fixed field list with "no
`referralCode` among them".

#175 proposed requiring `application/json`, which closes the form-encoded path
at the parser. 0016 and 0017 had each rejected that for the same reason: that
path is the one a supporter without JavaScript uses. #175 asked two questions
before deciding a third time:

- **How many genuine submissions arrive form-encoded?** APM could not answer
  this. Transaction events are kept for about eight days, and in that window
  production received three POSTs. All three were form-encoded, none looked
  like a supporter (one sent a `Chrome/58` user agent), and there were no JSON
  submissions to compare them with. The agent does not record `Origin` or
  `Referer` either: both are null even on a Cypress run's JSON post to the test
  API. Only the origin access log on the host covers a longer period.
- **Is there a middle option?** Yes, and it does not depend on the first answer.

## Decision

**A submission must carry `referralCode`. An empty value is accepted, and a
missing or non-empty one is refused** with the honeypot's existing `400`,
before any mail is sent. Both encodings and both submission endpoints
(`/send-email`, `/yard-sign`) are covered, because both endpoints go through
`_handle_form_submission`. No other route accepts a body.

Every real submission already carries the field:

- **No JavaScript.** The browser's form-submission algorithm includes every
  enabled, named input, and a text input with an empty value is still sent.
  CSS has no effect on this, so the field is sent although it is
  `display: none`. `tests/unit/honeypot.spec.ts` builds `new FormData(form)`
  from each rendered form, which runs the same algorithm. A later `disabled` or
  a lost `name` therefore fails in CI and not in a supporter's inbox.
- **Scripted.** Both composables send `referralCode: ''`. They have done so
  since 0016.

A JSON `null` counts as absent. A form field sent more than once is checked
across all of its values, so `referralCode=&referralCode=spam` is refused.
Neither shape comes from a form. A body that cannot be parsed is treated as
blank, not absent, so it still gets the parser's "must be valid JSON or form
data" `400`. `HONEYPOT_ENFORCED=false` switches off both checks. The refusal is logged either way (`was absent` or
`was filled`), with the body, as 0016 set up for a filled field.

## Consequences

- **Both observed cases are refused**, and the no-JavaScript path still works.
- **The bar is low, and it is placed where the observed traffic falls short.**
  Any client that reads the form completely, or reads this API's spec, sends
  the field and passes. What this stops is a bot that posts only the fields it
  has values for, and a bot that replays a fixed list. Those are the two kinds
  seen so far.
- **The field is now part of the API contract.** `openapi.yaml` marks it
  required, and every request example in the spec is posted to the app and must
  be accepted. The API's no-JavaScript test posts the field list in
  `tests/fixtures/no-js-form-fields.json`, and the frontend suite checks that
  list against each rendered form's `FormData`.
- **A page from before 2026-08-10** would have no field and would be refused,
  with a message that tells the person to email. HTML is served with a
  zero-second lifetime (`public/.htaccess`), so only a tab left open for six
  weeks could still hold one.

## Alternatives considered

- **Require `application/json`** (#175 as filed). It closes the same two cases
  and a few more, and it costs the no-JavaScript path. 0016 and 0017 already
  judged that cost too high. The presence check removes the specific reason to
  pay it now. Revisit if a bot starts sending the blank field. At that point it
  would be reading the form properly, and the question becomes what separates
  it from a browser.
- **Require a present `Origin`.** Every browser sends it on a cross-origin POST,
  and that includes the no-JavaScript form post. But nothing recorded whether
  the 2026-09-06 bot sent one, so nobody could say this would have caught it.
  0017 also allows an absent `Origin` on purpose. Reversing that is a separate
  decision, and it needs evidence this record does not have.
