# 0016. Add a persistent long-window rate limit and a form honeypot

**Status:** Accepted
**Date:** 2026-08-10

Amends [0009](0009-in-process-rate-limiting.md) and
[0014](0014-do-not-trust-forwarding-headers.md). 0014's decision — trust no
forwarding header unless one is configured — is unchanged and still governs how
a client is identified. What this record replaces is 0009's assumption that
process memory is a sufficient home for _every_ window.

## Context

On 2026-08-10 a single IP address posted 43 submissions to `/send-email` over
about twelve hours, 42 of them inside a two-hour burst. Every one succeeded.
New Relic recorded 36 of them (the rest predate the sampling window):

| Signal            | Value                                          |
| ----------------- | ---------------------------------------------- |
| `response.status` | `200` — 36 of 36                               |
| Mean duration     | 6.0s (max 12.7s)                               |
| `Content-Type`    | `application/x-www-form-urlencoded` — 36 of 36 |
| User-Agent        | **5 distinct values**, rotated                 |

Each success is expensive and externally visible: a notification email to the
campaign, **a confirmation email to whatever address the submitter supplied**,
and a row in the sheet the volunteers work from. So the incident cost roughly 86
messages through the campaign's own SMTP account and 43 junk rows — and the
confirmation leg means the endpoint will send mail to an arbitrary third party
on request, which is the exact mechanism by which a domain lands on a blocklist.
0009 named that outcome as the reason to have a limiter at all.

**The limiter could not have fired.** Measured over sliding windows, the traffic
peaked at 3 per minute, 6 per five minutes, 10 per ten minutes, 16 per half hour
and 23 per hour, against a shipped limit of 5 per 60 seconds. Nothing about the
pacing looks accidental, and the rotating User-Agent says the software is
evasion-aware. The IP was blocked in cPanel and the block was verified, which
resolves this instance and nothing about the next one.

Two further facts shaped the design.

**Process memory cannot hold an hour.** 0009 justified an in-memory limiter on
the grounds that there is "a single Passenger app, and in practice a single
long-lived worker". The measurement in
[../hosting.md](../hosting.md#watch-worker-memory), taken later for an unrelated
question, contradicts it: Passenger here "spawns them per request and reaps them
when idle — `ps` at a quiet moment returns _nothing at all_". A 60-second window
survives that, because repeat traffic inside a minute tends to reach a warm
worker. An hour-long window does not: this caller's median gap was 147 seconds,
with gaps up to 17 minutes, so it would plausibly meet a fresh worker and be
counted from zero nearly every time. Building the second tier on the first
tier's substrate would have produced a control that reads correctly, tests
green, and does nothing in production.

**No IP-keyed limit answers the actual threat.** The stated worry is a caller
who changes address, and against that a limiter of any window is worth exactly
one proxy. Something not keyed on the client is needed as well.

## Decision

Three changes, all in [../../api/](../../api/) plus the two form components.

**1. A second rate-limit tier, 10 requests per 3600 seconds**, per endpoint and
per client, configurable via `LONG_RATE_LIMIT_MAX_REQUESTS` and
`LONG_RATE_LIMIT_WINDOW_SECONDS`. It is consulted only for requests the burst
tier already allowed, so a caller cannot spend its hourly allowance on requests
that were refused. The number sits an order of magnitude above real use — a
genuine supporter submits one form once — and well below the 23/hour observed.

**2. That tier counts in SQLite**, in
[../../api/rate_limit_store.py](../../api/rate_limit_store.py), at
`api/tmp/rate-limit.sqlite3`. `sqlite3` is in the standard library, so this adds
no dependency and no service that can be down; `tmp/` is the one directory the
deploy's prune step (`find . -type f ! -path './tmp/*'`) leaves alone, so the
counters survive releases as well as worker churn. Time is wall clock rather
than `monotonic()`, because every value is written by one process and read by
another.

**The store fails open.** A limiter that cannot reach its database logs and
allows the request. The burst tier is still in front of it, and refusing a real
volunteer is the worse failure.

**3. A honeypot field on both forms.** A `referralCode` input hidden with
`display: none`; a submission that arrives with it non-empty is refused with
`400` before any mail is sent. This is the part that survives an IP change.

Three details of the honeypot are deliberate, and all three exist to protect the
same person:

- **`display: none`, never `.sr-only`.** A `display: none` element is removed
  from the accessibility tree, so assistive technology never encounters it. The
  off-screen idiom (`position: absolute; left: -9999px`) is the opposite — it is
  precisely how `.sr-only` keeps content available to screen readers. Swapping
  one for the other looks like an equivalent refactor and would turn this field
  into a trap only screen-reader users can fall into. CI's Lighthouse
  accessibility gate is `≥ 1.00` and axe skips `display: none` nodes, so a
  correct honeypot holds the score and a botched one fails the build.
- **The residual risk is autofill, not screen readers.** A password manager
  filling a hidden field would reject a real submission, so the field carries
  `autocomplete="off"`, `tabindex="-1"`, and a name that is not an autocomplete
  token and matches no common heuristic (`name`, `email`, `phone`, `address`,
  `organization`, `nickname`, `url` are all out).
- **A trip is logged with the body, and says so.** The response tells the person
  to email the campaign directly rather than offering a validation error they
  cannot act on — the field they would have to clear is invisible to them. The
  body goes to the log via the existing `_log_request_body` path, so a false
  positive is recoverable rather than lost. `HONEYPOT_ENFORCED=false` disables
  enforcement in cPanel without a deploy while still logging, which is what
  makes the switch usable as evidence.

## Implementation notes

Details of [../../api/rate_limit_store.py](../../api/rate_limit_store.py) that
are not obvious from reading it, and are the reason it is not three lines
shorter:

- **A new connection per call, never a pooled one.** Passenger forks workers and
  reaps them at idle, and a `sqlite3.Connection` carried across a fork shares an
  OS file descriptor and its locking state — a documented way to corrupt the
  file. Opening costs tens of microseconds against a request that already spends
  seconds in SMTP (measured mean 6.0s), so pooling would buy nothing and risk
  exactly that.
- **`BEGIN IMMEDIATE`, not the default deferred transaction.** The count and the
  insert that follows it have to be one atomic step. Deferred, two workers can
  both read the same count, both conclude they are under the limit, and the
  effective limit is one higher than configured for every concurrent pair.

  **Atomicity here actually has two independent guards**, which is worth knowing
  before refactoring either. The second is that the prune's `DELETE` runs before
  the `SELECT`: it is a write, so it takes the write lock regardless of how the
  transaction began. Measured over 25 runs of eight processes racing for one
  remaining slot:

  | Transaction       | Prune position | Callers admitted |
  | ----------------- | -------------- | ---------------- |
  | `BEGIN IMMEDIATE` | before count   | 1 (shipped)      |
  | `BEGIN`           | before count   | 1                |
  | `BEGIN IMMEDIATE` | after count    | 1                |
  | `BEGIN`           | after count    | **4–8**          |

  So either guard alone holds, and `test_concurrent_workers_cannot_both_take_the_last_slot`
  pins the property rather than either keyword. Moving the prune below the count
  looks like a harmless reordering and is safe only while `BEGIN IMMEDIATE`
  stays.

  The failure is also silent rather than loud: a deferred transaction losing the
  snapshot raises `SQLITE_BUSY`, which the fail-open handler below turns into an
  admission. Failing open is right for a database that cannot be reached, but it
  means lock contention degrades the limit rather than erroring — another reason
  the write lock must be taken up front rather than contended for.

- **WAL journalling**, so a reader is not blocked while another worker writes.
  It persists in the database header, so setting it per connection is a no-op
  after the first.
- **Expired rows are pruned on every call, across all keys**, rather than by a
  separate sweep. Rows are only useful for one window and the whole table is a
  few dozen rows at this traffic, so there is nothing to schedule.
- **`Retry-After` rounds up**, for the reason
  [0014](0014-do-not-trust-forwarding-headers.md) fixed in the in-memory tier:
  truncating advertises a retry still inside the window, so a client honouring
  the header exactly earns a second 429.
- **Failures log every time, not once per worker.** Failing open silently
  disables an abuse control; at two form endpoints on a municipal campaign site
  there is no traffic volume at which that line becomes spam — the busiest hour
  ever observed was 23 requests, and that was the attack.
- **`DEFAULT_DB_PATH` resolves relative to the module, not the process's cwd**,
  so it follows the package into whichever app root it was deployed to (`api/`
  in production, `api_test/` on the test subdomain) the same way
  `passenger_wsgi.py` aliases the package name.

## Consequences

- **The 2026-08-10 pattern is now capped at 10/hour per address** instead of
  unbounded, and the honeypot may stop it outright regardless of address.
- **Still no new infrastructure.** No Redis, no service to monitor, no
  dependency added to `requirements.txt`.
- **A new on-disk artefact exists on the host**, and it is runtime state rather
  than code: gitignored, excluded from the deploy prune, pruned of expired rows
  on every call. At this traffic the table holds a few dozen rows.
- **The two tiers can disagree about what a "client" is.** They do not today —
  both call `_rate_limit_key()` — but the persistent one would keep counting a
  key the in-memory one had evicted under `RATE_LIMIT_MAX_BUCKETS` pressure.
  That is the safe direction.
- **A shared NAT shares the hourly bucket**, as 0009 already noted for the
  per-minute one. Eleven volunteers signing up within an hour from one office or
  campus network would see a 429 — they are told to retry, not turned away, and
  the limit is per endpoint so the other form still works.
- **The honeypot can reject a real person.** It is the only feature on the site
  that can, which is why it logs the body, explains an alternative route, and
  has an env kill switch. If it ever fires on someone real, turn it off and read
  the log before deciding.
- **Worker lifetime is now load-bearing documentation.** The claim that Passenger
  reaps idle workers is what justifies the SQLite store over the simpler
  in-memory one. It is measured in
  [../hosting.md](../hosting.md#watch-worker-memory) rather than assumed, and
  `test_counts_survive_a_separate_process` fails if the store stops being
  durable.

## Alternatives considered

- **A longer window in process memory.** The change the incident first suggested,
  and the one this record exists to argue against: it would have been defeated
  by the same worker recycling that hosting.md documents, while looking correct
  in review and in tests.
- **A global unkeyed cap on submissions per hour.** The only thing that truly
  bounds SMTP damage under a distributed attack, and the only one that can turn
  away a real supporter during a genuine surge — a yard-sign push or a debate
  night. Not worth that trade for a threat that has so far arrived from one
  address; revisit if abuse recurs from many.
- **Blocking `application/x-www-form-urlencoded`.** All 36 captured requests used
  it while the site's scripted path posts JSON, so it is a strong signal. It is
  also exactly the no-JavaScript submission path the forms deliberately support,
  and breaking that to catch a bot inverts the priority.
- **CAPTCHA / Turnstile.** 0009 declined it on conversion grounds and that still
  holds; the honeypot is the version of this idea that costs no interaction.
- **Redis, or a database.** Correct across processes, and still unavailable on a
  shared host — which is what makes the standard library's SQLite the right
  answer rather than a compromise.
