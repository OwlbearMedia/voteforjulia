# Monitoring

What watches the site, what will page you, and how to tell a real outage from a
false alarm.

Why it is set up this way is [ADR-0013](adr/0013-server-side-apm.md) (and
[ADR-0011](adr/0011-browser-side-observability.md), which it supersedes). The
agent's environment variables and the host's resource limits are in
[hosting.md](hosting.md#new-relic-agent-environment).

## The account

Everything lives in New Relic account **8127277**. Three things report into it:

| Source         | Reports as              | Configured in                                 |
| -------------- | ----------------------- | --------------------------------------------- |
| Browser agent  | `voteforjulia`          | [src/lib/newrelic.ts](../src/lib/newrelic.ts) |
| Production API | `voteforjulia-api`      | cPanel env vars on the `api` app              |
| Test API       | `voteforjulia-api-test` | cPanel env vars on the `api_test` app         |

The browser agent's licence and application IDs are public by design and live in
client code. The APM licence key is an **ingest** key set per app in cPanel —
not the `NRAK-` user key the source map upload uses. They are different
credentials and the agent fails silently with the wrong one.

## Configuration lives in this repo

New Relic has no export-to-git story, so the definitions are kept here by hand:

- **[monitoring/dashboard.json](../monitoring/dashboard.json)** — the "Vote for
  Julia — Site Health" dashboard, 20 widgets across two pages. Re-import via
  Dashboards → Import dashboard, or push it with the API as described
  [below](#pushing-dashboardjson-back-to-new-relic). Live and file agreed as of
  2026-08-20.
- **[monitoring/alerts.graphql](../monitoring/alerts.graphql)** — the synthetic
  monitors, both alert policies, their conditions, and the notification
  destination, channels and workflows, as NerdGraph mutations.

**These drift.** Nothing syncs them; editing a widget in the UI does not update
the file. If you change something in New Relic, change it here too, or the next
person to need it rebuilds from a stale copy. To pull the live dashboard back
down, use the `get_dashboard` NerdGraph query on the dashboard's GUID — note it
omits widget `layout`, so merge rather than overwrite.

There is also an older `voteforjulia` dashboard from 2026-06-02, predating this
setup and not tracked here.

### Pushing dashboard.json back to New Relic

**`monitoring/dashboard.json` is an _export_ artifact and `dashboardUpdate` will
not accept it unmodified.** The UI's Import dashboard reads export format, so
for a one-off that is still the shortest path. Going through the API needs two
corrections, and both fail loudly enough to waste an evening:

- **`link` is a string on export and an object on input.** The JavaScript error
  detail widget carries `"link": "https://…"`; `DashboardWidgetLinkInput` wants
  `{ url: "https://…" }`. Nothing else in the file has this shape.
- **`rawConfiguration` is a JSON scalar, so it must be passed as a GraphQL
  variable.** Inlined into the query document it is parsed as an object literal
  and validated field by field, which produces `Unknown field` for every
  `nrqlQueries`, `platformOptions`, `thresholds`, `facet` and `yAxisLeft` in the
  file — one error per widget, and none of them says what is actually wrong.

**Prefer `dashboardUpdateWidgetsInPage` to a whole-dashboard update.** It takes
the page GUID and the widgets you actually changed, so untouched widgets are
never round-tripped through the conversion above, and a widget you did not
intend to edit cannot be quietly reshaped by it. Widget `id`s and page GUIDs
come from the entity:

```
newrelic nerdgraph query 'query { actor { entity(guid: "<DASHBOARD_GUID>") {
  ... on DashboardEntity { pages { guid name widgets { id title } } } } } }'
```

Then send `{"guid": "<PAGE_GUID>", "widgets": [...]}` as a variables file, each
widget carrying `id`, `title`, `visualization`, `layout` and `rawConfiguration`
copied from this repo's copy:

```
newrelic nerdgraph query 'mutation($guid: EntityGuid!, $widgets: [DashboardUpdateWidgetInput!]!) {
  dashboardUpdateWidgetsInPage(guid: $guid, widgets: $widgets) { errors { description type } } }' \
  --variablesFile widgets.json
```

The dashboard is `ODEyNzI3N3xWSVp8REFTSEJPQVJEfGRhOjEyOTczMDE2`; its Overview
page is `ODEyNzI3N3xWSVp8REFTSEJPQVJEfDUwMDIwODk5`.

**Read the widgets back afterwards.** `dashboardUpdateWidgetsInPage` returns
`errors: null` on success, and the New Relic CLI prints `{}` for a successful
mutation as readily as a failed one — see the note at the top of
[alerts.graphql](../monitoring/alerts.graphql). Neither is evidence the change
landed.

## What is watched

### Synthetic monitors

Both probe `/health/deep`, which unlike `/health` actually authenticates against
SMTP and reads spreadsheet metadata — see
[architecture.md](architecture.md) for why there are two health endpoints.

| Monitor                              | Target     | Period | Alerts? |
| ------------------------------------ | ---------- | ------ | ------- |
| `voteforjulia-api /health/deep`      | production | 15 min | **yes** |
| `voteforjulia-api-test /health/deep` | test       | 30 min | no      |

**The periods are a billing constraint, not a tuning choice.** Both were
lengthened on 2026-08-10 — production from 5 min, test from 15 — because
5-minute checks ran over the plan's budget. Two things follow, and both are
easy to miss:

- **The alert's aggregation window has to track the period.** See the
  [alert conditions](#alert-conditions) below; changing one without the other
  stops the alert firing at all.
- **`/health/deep` has its own rate-limit allowance** (30/hour, against the
  form endpoints' 10) so a monitor can never 429 itself into a false alert.
  `test_health_deep_allowance_fits_the_synthetic_monitor` in
  [api/test_app_pipeline.py](../api/test_app_pipeline.py) fails if a future
  period change outgrows it. Raise the allowance before shortening the period.
- **Its results are cached for 60 seconds**
  ([ADR-0017](adr/0017-origin-trust-boundary-and-health-probe-cache.md)), so the
  endpoint cannot be used as an amplifier against SMTP and Sheets. At a 15- or
  30-minute period every scheduled check still runs the real probes, and the
  `Age` response header says which it got — `0` means the probes ran for that
  request. **Keep any future period comfortably above the TTL**: a period below
  it would have the monitor grading a cached answer, and an outage could clear
  and re-alert against a result nothing re-measured.

**The test monitor is deliberately not wired to the policy.** Every PR deploy
restarts `api_test` and it briefly fails. Alerting on that would train you to
ignore alerts, which is worse than not having them.

Two details in the monitor config that look optional and are not:

- **`shouldBypassHeadRequest: true`** — a SIMPLE monitor sends `HEAD` by
  default, which returns no body, and the body is the entire check.
- **The validation string is `"status":"ok"` with no space.** Flask's `jsonify`
  emits compact JSON. A copy taken from pretty-printed output never matches.

### APM data here is a sample, not a census

**Read this before trusting any `Transaction` number in this document.**

Measured on 2026-08-19 over the preceding seven days:

| Signal                               | Volume                |
| ------------------------------------ | --------------------- |
| `SyntheticCheck` for `/health/deep`  | 192/day, 100% SUCCESS |
| `Transaction` for `voteforjulia-api` | 1–11 per **6 hours**  |

192 successful probes a day should produce about 192 transactions a day. APM
records roughly 3% of them.

The cause is in [hosting.md](hosting.md#watch-worker-memory): this host "spawns
them per request and reaps them when idle". The agent harvests on a 60-second
cycle and registers with the collector in a background thread, so a worker that
serves one probe and is reaped ships nothing. Under sustained load workers live
long enough to harvest, so the loss is **biased toward idle periods** rather
than uniform — which means recorded counts cannot be scaled back up by any fixed
factor.

Two consequences worth stating plainly:

- **`SyntheticCheck` is the only complete signal in this account.** It is
  produced by New Relic's infrastructure, not by a process this host can reap.
  Alert conditions belong on it wherever they can be.
- **An absolute count degrades more honestly than a percentage.** A ratio
  implies a denominator this host cannot supply. A count says "at least this
  many", which is what a sample actually supports.

This is why the conditions below changed shape on 2026-08-19. See
[ADR-0021](adr/0021-alert-on-signals-the-host-cannot-drop.md).

### Alert conditions

**There are two policies.** Both notify only Dylan; the split marks which
alerts mean supporters are being turned away, as opposed to something only the
engineer cares about. It exists because a notification path to the candidate was
built against it and then abandoned — see
[ADR-0022](adr/0022-do-not-automate-the-candidates-alerts.md), which also
records that this is structure kept past its original reason. Both are
`PER_CONDITION`, so an SMTP outage and a Sheets outage open separate issues
rather than collapsing into one.

Read back from the account on 2026-08-19, after the rebuild:

| Policy                            | ID        | Holds                                         |
| --------------------------------- | --------- | --------------------------------------------- |
| `voteforjulia — API`              | `7831111` | engineer-facing conditions                    |
| `voteforjulia — Campaign visible` | `7922533` | conditions meaning supporters are turned away |

| Condition                                        | ID         | Policy    | Fires when                                                                             |
| ------------------------------------------------ | ---------- | --------- | -------------------------------------------------------------------------------------- |
| API dependency check failing (production)        | `66281097` | `7922533` | the production synthetic fails twice in a row                                          |
| Rate limiter tripping — hourly tier (production) | `66284763` | `7922533` | any recorded hourly refusal on the **form** endpoints in two consecutive 5-min windows |
| Synthetic monitor not running (production)       | `66281163` | `7831111` | no synthetic check for 45 minutes                                                      |
| API serving 5xx (production)                     | `66281170` | `7831111` | any 5xx in a 5-minute window                                                           |
| Rate limiter tripping — burst tier (production)  | `66284760` | `7831111` | >3 recorded burst refusals per 5 min, sustained 15 minutes                             |

All five were read back from the account on 2026-08-20 and are enabled.

**Adding a condition means choosing a policy, and adding a policy means adding
a workflow.** A channel belongs to exactly one workflow, so a third policy
created without its own workflow and channel raises issues that reach nobody —
which is exactly the state this account was in before 2026-08-19.

### The outage alert was dead for nine days

Worth knowing because the same shape will recur. Until 2026-08-19 the live
`API dependency check failing` ran with `aggregationWindow: 300` and
`thresholdDuration: 600` — the values from before the monitor moved to a
15-minute period on 2026-08-10. `alerts.graphql` was corrected that day; the
live condition was not.

At a 900-second period against 300-second windows, checks land in one window of
every three and the rest fill with zero, so the two consecutive breaching
windows `thresholdOccurrences: ALL` requires can never occur. **It could not
fire.** This page had described that exact mechanism, flagged the live values as
unverified, and named the check that would settle it — and the check was
impossible, because the read-only MCP server cannot return a condition's
`signal`. With a user API key it is one query. Re-read it after any period
change:

```
newrelic nerdgraph query 'query { actor { account(id: 8127277) { alerts {
  nrqlCondition(id: "66281097") { ... on AlertsNrqlStaticCondition {
    name signal { aggregationWindow } terms { thresholdDuration } } } } } } }'
```

**Two conditions were retired on 2026-08-19, both for the sampling reason
above:**

- **`API error rate above 5%` (`64880233`) was a bot detector.** It asked for
  `percentage(count(*), WHERE error IS true)`. The `error` intrinsic is set only
  when an exception reaches the agent, and over 30 days the only transactions
  carrying it were **12 HTTP 405s from bots probing with the wrong method** —
  4.5% against a 5% threshold. Replaced by `API serving 5xx`, which reads the
  status code and needs no exception.
- **`API not reporting` (`64880240`) fired on healthy days.** It counted
  `Transaction` with empty windows filled to 0, so it was measuring worker
  lifetime. It opened issue `6d261d33` on 2026-08-17 during a stretch when the
  synthetic was 192/192 green. Replaced by `Synthetic monitor not running`,
  which asks the same question — is anything still watching? — of data this host
  cannot drop.

### The rate-limit thresholds are counted in a ~11% sample

Measured on 2026-08-20 by deliberately tripping the limiter against production:
**9 refusals generated, 1 recorded.** That is better than the ~3% baseline
above — a burst keeps a worker alive long enough to harvest — and still an
order of magnitude of loss.

Both rate-limit thresholds are therefore counted in _recorded_ refusals and are
roughly 10x smaller than the real number they stand for:

| Condition   | Recorded threshold                  | Implies roughly     |
| ----------- | ----------------------------------- | ------------------- |
| burst tier  | >3 per 5 min, sustained 15 min      | ~30 real per window |
| hourly tier | >0 in two consecutive 5-min windows | ~10 real per window |

The first draft used 20 and 5, which would have needed ~180 and ~45 real
refusals per window. Both would have been silent through anything short of a
sustained attack. **If you change the sampling — a longer-lived worker, a
different host, `NEW_RELIC_STARTUP_TIMEOUT` — re-measure before trusting these
numbers.**

To re-measure, trip the limiter yourself and compare. Use `/health/deep`, not a
form endpoint: it is cached, rate-limited by design, and sends no email and
writes no spreadsheet row. Your own address keys a different bucket from the
synthetic's, so this cannot starve the monitor.

```
for i in $(seq 1 24); do curl -s -o /dev/null -w "%{http_code} " \
  https://api.voteforjulia.com/health/deep; sleep 4; done
```

Then, after a harvest cycle:

```
SELECT count(*) FROM Transaction
WHERE `rate_limit.tier` IS NOT NULL FACET `rate_limit.tier`, `rate_limit.scope`
SINCE 30 minutes ago
```

**Both tiers are cross-worker as of 2026-08-26**
([ADR-0024](adr/0024-count-every-rate-limit-tier-in-sqlite.md)), so either is
deterministic to test against: five rapid requests are allowed and the sixth is
refused, whichever worker each one lands on.

This section used to say the opposite, and the correction is why the thresholds
below need re-measuring. `_RATE_LIMIT_BUCKETS` was a module-level dict, so each
Passenger worker kept its own count and the effective ceiling was 5 x however
many workers were alive — measured on 2026-08-20, seven rapid requests did not
trip it and the first refusal came at about fifteen. **The burst tier therefore
refuses more traffic now than it did when its threshold was calibrated.** Expect
that condition to be noisier until it is re-measured.

**The hourly condition may go quieter, and that is not the same as things being
calm.** A caller bursty enough to leak past a per-worker burst tier used to
reach the SQLite hourly tier and be refused there, producing the `hourly`
refusals that the on-policy, campaign-visible condition counts. Stopped at
`burst` now, they produce none. The patient caller that tier was actually built
for — the 2026-08-10 shape, 23 an hour and never three in a minute — is
unaffected, so the condition still catches what it was sized against.

**Conditions existing is not the same as being alerted.** A policy with no
notification workflow and destination raises issues that sit in the UI and reach
nobody, which looks identical to "nothing has gone wrong". Confirm a workflow
exists (Alerts → Workflows) and send yourself a test notification; that is the
only check that proves the path end to end.

**Two conditions are coupled to the synthetic's period**, and neither dependency
is visible from the New Relic UI. This page used to say the live values were
unverified because the read-only MCP server cannot return a `signal` block —
**that is no longer true and the answer was bad**: read back on 2026-08-19 the
dependency check still held the 5-minute values and had been unable to fire for
nine days (above). Both were rebuilt correctly. With a user API key this is one
query, so verify rather than assume after any period change:

```
newrelic nerdgraph query 'query { actor { account(id: 8127277) { alerts {
  nrqlCondition(id: "66281163") { ... on AlertsNrqlStaticCondition {
    name signal { aggregationWindow } terms { thresholdDuration } } } } } } }'
```

- **"API dependency check failing" — keep `aggregationWindow` equal to the
  period and `thresholdDuration` at twice it.** At the current 15 minutes that
  is 900 and 1800. The condition fills empty windows with 0 and requires _every_
  window in `thresholdDuration` to breach, so a window shorter than the period
  guarantees a filled zero between checks and the breach can never be sustained.
  It then fails silently, which is the worst way for an alert to fail. Detection
  now takes about 30 minutes — the cost of the longer period, not a choice.
- **"Synthetic monitor not running" has the same coupling**, for the same
  reason: `aggregationWindow` 900 equals the period, and `thresholdDuration`
  2700 is three consecutive empty windows. Lengthening the monitor period
  without lengthening both would have it firing between ordinary checks.

### Julia is not on the alerting

**Nothing in New Relic emails the candidate.** Both workflows go to
`dylan@voteforjulia.com` and her address is not stored in the account. If the
site is turning supporters away, telling her is a phone call, not a
notification.

This was built and then removed on 2026-08-19, and the reason is worth knowing
before anyone rebuilds it: **New Relic's EMAIL channel does not let you write
the email.** The schema exposes `subject` and `customDetailsEmail`, and the
label on the second one is literally "Additional information to put in the
email" — it is appended below a priority badge, the raw issue title, a **Go to
issue** button, alert-event counts, and a table containing the policy name, the
condition name and the NRQL. The subject is ours and reads well; nothing under
it does. Full reasoning, including why a relay through this API would fail at
exactly the wrong moment, is in
[ADR-0022](adr/0022-do-not-automate-the-candidates-alerts.md).

The live notification objects, read back on 2026-08-19:

| Object      | Name                              | Notes                                   |
| ----------- | --------------------------------- | --------------------------------------- |
| Destination | `Dylan Whitney`                   | the only destination in the account     |
| Channel     | `Dylan - all alerts`              | used by the API-policy workflow         |
| Channel     | `Dylan - campaign visible alerts` | a second channel is required, see below |
| Workflow    | `Dylan - voteforjulia API policy` | policy `7831111`, all three triggers    |
| Workflow    | `Dylan - campaign visible policy` | policy `7922533`, all three triggers    |

Three things about this will surprise you at the wrong moment:

- **A channel belongs to exactly one workflow.** Reusing one is rejected with
  `Channels ids are already in use by workflows [...]`, which is why there are
  two identical channels on one destination.
- **`notificationTriggers` must contain `ACTIVATED`.** A workflow that fires
  only on acknowledgement or closure cannot be created.
- **`violationTimeLimitSeconds` force-closes an issue that is still breaching**,
  and a force-close sends a resolved notification. Both campaign-visible
  conditions are set to 2592000 (30 days) rather than the 259200 default, so a
  long outage does not quietly report itself fixed.

## When something fires

### Is it real?

**Read the check duration before anything else. It usually names the failing
dependency on its own.** Each probe runs under its own timeout — 10s for SMTP,
15s for Sheets ([api/config.py](../api/config.py)) — and a healthy
`/health/deep` is about 1.5s: an SMTP handshake well under a second plus a
Sheets metadata read of a few hundred milliseconds. A failed check whose
duration sits just above one of those bounds has therefore already told you
which dependency hung, before you open a single log.

```
SELECT timestamp, locationLabel, result, error, duration
FROM SyntheticCheck WHERE monitorName = 'voteforjulia-api /health/deep'
SINCE 3 hours ago ORDER BY timestamp ASC
```

- **~16.5s** → Sheets. A normal SMTP handshake plus one 15s Sheets timeout.
- **~10s, or a multiple of it, plus a normal Sheets read** → SMTP. The figure
  to recognise is 10s rather than exactly 10s: `SMTP_TIMEOUT_SECONDS` bounds
  each socket operation, not the session, and a login is a dozen or so of them
  (see `_SMTP_OPERATIONS_PER_SESSION` in [api/app.py](../api/app.py)), so a
  server that stalls on several drags the probe out to a multiple.
- **Fast, or no 503 at all** → the app did not answer. A **520** is Cloudflare
  reporting that the origin returned nothing parseable, which is a dead worker
  rather than a failed probe.

Both probes always run — `_run_deep_health_probes` does not short-circuit when
SMTP fails — so the two figures add rather than replace each other.

Read the _successful_ checks either side too. Latency climbing toward a timeout
and then falling back is a transient upstream slowdown, not a broken
credential.

**Worked example, 2026-08-21.** The one real firing of this condition so far.
Sheets latency ramped over about an hour — 3.2s, 5.8s, 9.8s, then a 15.9s
check that still _passed_ because it came in just under the timeout — before
two checks crossed 15s and returned 503. Durations then fell to ~1.6s and
stayed there. The single error line in New Relic read
`Deep health check failed for sheets`, and the failing check took 16.583s
against a 15.0s Sheets timeout. Nothing was wrong with SMTP, which had accepted
mail 33 minutes earlier and did so again afterwards.

**Trust the timestamp, not the tail of `stderr.log`.** That file is appended to
across restarts and carries no visible boundary between one incident and the
next, so an unrelated traceback from weeks ago sits there reading as current.
On 2026-08-21 the first thing found in it was a block of SMTP authentication
errors from an entirely different period, which pointed the whole diagnosis at
the wrong dependency. Match the log line's timestamp to the failed check's
before believing it. A Sheets failure is easy to misread this way in its own
right: `verify_sheets_access` refreshes an OAuth token, so its traceback is
dense with `google.auth` frames and looks like an authentication problem at a
glance.

**Check whether every location failed at once.** The next-fastest
discriminator, and the one thing that is not obvious from the UI:

```
SELECT monitorName, result, locationLabel, responseStatus
FROM SyntheticCheck WHERE result = 'FAILED' SINCE 2 hours ago
```

- **All locations failed within the same minute** → the endpoint really is
  broken. Nothing about a genuine outage is location-specific.
- **One location failed while others passed** → nothing about the API is
  location-specific, so suspect something between the probe and the app. The
  known candidate is the
  [Imunify360 WAF](hosting.md#imunify360-waf-disabled), which challenges by
  source IP reputation and would flag the AWS ranges synthetics run from. A
  challenged request returns **HTTP 200** with a verification splash, so the
  status code looks healthy and only the response validation catches it — a
  false positive on a working API.

  **Every hostname it could affect has been excluded since 2026-08-15** — the
  2026-08-01 request this page credited until now covered
  `test.voteforjulia.com` alone, and the rest went on being challenged for two
  more weeks ([hosting.md](hosting.md#imunify360-waf-disabled)). So this should
  not happen now, which is what makes a single-location failure worth taking
  seriously as evidence the WAF is back rather than dismissing as noise.

  **A genuine dependency failure can still look location-specific, so run the
  duration check above before acting on this one.** Both 2026-08-21 failures
  were Columbus with San Francisco green between them, which reads as the WAF
  and was not: Sheets was slow for every caller, and which 15-minute poll
  happened to cross the 15s timeout was chance. Two locations at a 15-minute
  period is a coarse sample, and an intermittent fault lands on one of them
  more often than the phrase "one location" suggests.

### A 503 from the submission cap

`API serving 5xx` counts these, deliberately — the site turning supporters away
is worth knowing about.

**This page claimed until 2026-08-19 that `API error rate above 5%` counted
them. It did not.** That condition tested `error IS true`, which the agent sets
only when an exception reaches it. A 503 from the cap is a `jsonify` response
with a status code assigned — nothing raises, so nothing was counted, and the
condition would have stayed green through every shed submission. The replacement
reads `response.status` directly, which is why it works. The same mistake would
have hidden every 429; see [ADR-0021](adr/0021-alert-on-signals-the-host-cannot-drop.md).

Tell them apart from a genuine fault by the log line, which names the cap:

```
/send-email refused: 12 submissions already in flight
```

That is not a bug report. It means twelve submissions were being served at once,
and the usual cause is SMTP or Sheets responding slowly enough that ordinary
traffic stacks up — so check `/health/deep` before looking at the form code at
all. Raising `MAX_CONCURRENT_SUBMISSIONS` is the wrong first move: the cap is
sized against the account's memory limit, and lifting it trades a shed
submission for an LVE fault that takes the whole account down.
See [ADR-0018](adr/0018-cap-concurrent-submissions.md).

### A rate limiter tripping

**Usually this is good news.** A tripped limiter is a refused request, and the
overwhelming majority of refused requests here are scanners. The alert exists so
that the rare case — a real supporter who cannot submit a form — is not
invisible, not because every trip needs action.

Which tier fired says most of what you need:

```
SELECT count(*) FROM Transaction
WHERE appName = 'voteforjulia-api' AND `rate_limit.tier` IS NOT NULL
FACET `rate_limit.tier`, `rate_limit.scope` SINCE 6 hours ago
```

- **`burst`** (5 per 60s, counted across every worker since
  [ADR-0024](adr/0024-count-every-rate-limit-tier-in-sqlite.md)) — someone in a
  hurry. A double-click, a retry loop, a scanner. Almost never worth acting on
  alone.
- **`hourly`** (10 per hour, [ADR-0016](adr/0016-second-tier-rate-limiting-and-honeypot.md))
  — a caller that paced itself under the burst limit for an hour. That is either
  deliberate abuse or a supporter genuinely stuck in a retry loop, and it is the
  one worth acting on.

`rate_limit.scope` names the endpoint (`send-email`, `yard-sign`,
`health-deep`). **`health-deep` trips are almost always a scanner** hammering
the probe, which is harmless and needs nothing. The one case worth acting on is
the monitor refusing _itself_: it has a 30/hour allowance sized against its
period, and if those have drifted apart it is now grading its own 429s. Tell
them apart by the source — a monitor trip coincides with `SyntheticCheck`
failures, a scanner's does not. If it is the monitor, raise the allowance rather
than touching the alert.

The hourly condition filters to `send-email` and `yard-sign` and deliberately
excludes `health-deep`: a scanner exhausting the probe's allowance says nothing
about whether a supporter can submit a form, and this is the condition that
marks an alert as campaign-visible.

**The client address is deliberately not recorded**, so New Relic cannot tell
you who was refused ([ADR-0014](adr/0014-do-not-trust-forwarding-headers.md)).
If you need that, it is in the host's `~/api/stderr.log`, not here.

Counts here are a floor, not a total — see
[APM data here is a sample](#apm-data-here-is-a-sample-not-a-census). The
thresholds on both conditions were set without data and should be tuned once
there is a week of it.

### If it is real

`/health/deep` reports which dependency broke:

```
curl -s -D /dev/stderr https://api.voteforjulia.com/health/deep | jq
```

`-D /dev/stderr`, not `-D -`: the latter writes the headers to stdout, where
they reach `jq` ahead of the body and it dies on `HTTP/2 200` instead of showing
you the probe result.

Read `Age` from the headers first. Anything above `0` is a cached result, so a
green answer may predate the alert by up to a minute — wait it out and ask
again rather than concluding the alert was noise.

- `"smtp": "fail"` → the mail server or its credentials. This is the
  2026-07-30 failure mode; check `EMAIL_PASSWORD` for a `$`
  ([hosting.md](hosting.md#app-env-vars-must-not-contain-)) before anything else.
- `"sheets": "fail"` → service account credentials, or the sheet stopped being
  shared with it — but check the failed check's duration before assuming
  either. A probe that took ~16.5s hit the 15s timeout, which is Google being
  slow rather than anything about the credentials, and is the one cause
  observed so far (2026-08-21). Credentials fail fast.

The response deliberately says only `fail` — the underlying exception text
quotes credentials, so it is never returned to an unauthenticated caller. The
detail goes to the agent instead, and **`Log` is the copy to reach for first**:

```
SELECT timestamp, message, level FROM Log
WHERE message LIKE 'Deep health check failed%' SINCE 24 hours ago
```

One line per failed probe, naming the dependency. Observed to survive at least
one case where the agent's copy below did not (2026-08-21); the reason it does
has not been established, so treat it as the more reliable of the two rather
than as guaranteed.

The same failure is also tagged on the agent's side, which adds the exception
class and the traceback:

```
SELECT count(*) FROM TransactionError
WHERE appName = 'voteforjulia-api' FACET health.dependency, error.class
SINCE 24 hours ago
```

**Do not read an empty result here as "no failure".** This is the sampling
above, and a health probe is its worst case: one failing check on an otherwise
idle host is exactly the pattern Passenger reaps before the agent's 60-second
harvest. On 2026-08-21 this query returned nothing for the incident window —
New Relic recorded a single `deep_health_check` transaction across those seven
hours, a 200 — while the `Log` query above returned the line that identified
Sheets. Over three days APM held 55 of ~576 checks, about 10%.

[ADR-0021](adr/0021-alert-on-signals-the-host-cannot-drop.md) records the
opposite expectation — that this attribute "is still how a 503 gets attributed
to SMTP or Sheets after the fact; that use never needed completeness". The
first real firing of the condition showed it does need completeness: with one
failing probe rather than a run of them, a 10% sample usually holds nothing.
The attribute is still worth having when it lands, for the traceback. It is not
the thing to check first.

That attribute exists because the first version swallowed the exception
entirely: nine production 503s recorded a status code and nothing else, and
finding out they were all Sheets took an SSH session into
`~/api/stderr.log`. The full traceback is still there if neither copy above is
enough — but see the warning about that file's timestamps in
[Is it real?](#is-it-real).

### Stale Sheets connections

The failure to expect, because it has already happened: `BrokenPipeError` from
Google Sheets. The client is cached for the worker's lifetime and its
keep-alive socket gets closed while idle, so the next call writes into a dead
connection.

Reads rebuild the client and retry once. **The append deliberately does not** —
a connection error surfaces while reading the response, which cannot be told
apart from a request the server already applied, so a retry could duplicate a
supporter's row. It clears the cached client and fails, which returns a 502 and
logs the raw body for recovery.

One useful side effect: `/health/deep` exercises the same cached client on every
probe, so a stale connection is often discovered and discarded before a real
submission meets it. Two things keep that a mitigation rather than a guard. The
cache is a module-level dict in
[sheets_service.py](../api/services/sheets_service.py), so it is **per Passenger
worker** — a probe refreshes only the worker that served it, and a submission
routed to any other worker still meets that worker's own idle socket. And
**lengthening the monitor's period widened the gap**: at the current 15 minutes
the window in which a submission can be the first caller to touch a dead socket
is three times what it was at 5.

### Turning it off

Clearing `NEW_RELIC_LICENSE_KEY` on an app and restarting disables the agent
without a deploy. That is the escape hatch if the agent itself ever becomes the
problem.

## Querying it

Some NRQL specifics for this account that cost time to rediscover:

- **`parseUrl()` is gated behind an unenabled beta flag.** Split environments
  with `FACET CASES (WHERE pageUrl LIKE ... AS '...')` instead.
- **One browser app holds production, test, and localhost traffic.** Filter with
  `WHERE pageUrl NOT LIKE '%localhost%' AND pageUrl NOT LIKE '%test.voteforjulia%'`,
  which is what every production widget in the dashboard does.
- **A deleted monitor's checks stay in `SyntheticCheck`.** An `API Health`
  monitor from the initial setup still has rows, so filter by `monitorName`.
- **Core Web Vitals are in seconds**, not milliseconds — an INP threshold of
  `0.2` is 200ms.
