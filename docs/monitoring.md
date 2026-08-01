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
  Dashboards → Import dashboard.
- **[monitoring/alerts.graphql](../monitoring/alerts.graphql)** — the synthetic
  monitors, the alert policy, and its three conditions, as NerdGraph mutations.

**These drift.** Nothing syncs them; editing a widget in the UI does not update
the file. If you change something in New Relic, change it here too, or the next
person to need it rebuilds from a stale copy. To pull the live dashboard back
down, use the `get_dashboard` NerdGraph query on the dashboard's GUID — note it
omits widget `layout`, so merge rather than overwrite.

There is also an older `voteforjulia` dashboard from 2026-06-02, predating this
setup and not tracked here.

## What is watched

### Synthetic monitors

Both probe `/health/deep`, which unlike `/health` actually authenticates against
SMTP and reads spreadsheet metadata — see
[architecture.md](architecture.md) for why there are two health endpoints.

| Monitor                              | Target     | Period | Alerts? |
| ------------------------------------ | ---------- | ------ | ------- |
| `voteforjulia-api /health/deep`      | production | 5 min  | **yes** |
| `voteforjulia-api-test /health/deep` | test       | 15 min | no      |

**The test monitor is deliberately not wired to the policy.** Every PR deploy
restarts `api_test` and it briefly fails. Alerting on that would train you to
ignore alerts, which is worse than not having them.

Two details in the monitor config that look optional and are not:

- **`shouldBypassHeadRequest: true`** — a SIMPLE monitor sends `HEAD` by
  default, which returns no body, and the body is the entire check.
- **The validation string is `"status":"ok"` with no space.** Flask's `jsonify`
  emits compact JSON. A copy taken from pretty-printed output never matches.

### Alert conditions

All three sit on the **`voteforjulia — API`** policy (`PER_CONDITION`, so an
SMTP outage and a Sheets outage open separate issues rather than collapsing into
one).

| Condition                    | Fires when                                    |
| ---------------------------- | --------------------------------------------- |
| API dependency check failing | the production synthetic fails twice in a row |
| API error rate above 5%      | >5% of transactions error for 5 minutes       |
| API not reporting            | no transactions for 30 minutes                |

The third exists because **silence is not a signal**. If the worker dies or the
agent crashes, error _rate_ has no data to be high on, so it uses
`fillOption: STATIC, fillValue: 0` to make absence look like zero throughput.

## When something fires

### Is it real?

**Check whether every location failed at once.** This is the fastest
discriminator and it is the one thing that is not obvious from the UI:

```
SELECT monitorName, result, locationLabel, responseStatus
FROM SyntheticCheck WHERE result = 'FAILED' SINCE 2 hours ago
```

- **All locations failed within the same minute** → the endpoint really is
  broken. Nothing about a genuine outage is location-specific.
- **One location failed while others passed** → suspect the
  [Imunify360 WAF](hosting.md#an-imunify360-waf-sits-in-front-of-litespeed). It
  challenges by source IP reputation, and synthetic checks come from AWS ranges
  that get flagged. A challenged request returns **HTTP 200** with a
  verification splash, so the status code looks healthy and only the response
  validation catches it — as a false positive on a working API.

### If it is real

`/health/deep` reports which dependency broke:

```
curl -s https://api.voteforjulia.com/health/deep | jq
```

- `"smtp": "fail"` → the mail server or its credentials. This is the
  2026-07-30 failure mode; check `EMAIL_PASSWORD` for a `$`
  ([hosting.md](hosting.md#app-env-vars-must-not-contain-)) before anything else.
- `"sheets": "fail"` → service account credentials, or the sheet stopped being
  shared with it.

The response deliberately says only `fail` — the underlying exception text
quotes credentials, so it is logged server-side and never returned. For the
actual error, look at the transaction in New Relic or the Passenger log.

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
