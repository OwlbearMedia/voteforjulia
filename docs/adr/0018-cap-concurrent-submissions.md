# 0018. Cap concurrent submissions, and close three smaller gaps

**Status:** Accepted
**Date:** 2026-08-13

Completes the review that produced
[0017](0017-origin-trust-boundary-and-health-probe-cache.md). That record
answered who may submit and what a probe may cost; this one answers how much
work may run at once, and tidies three smaller findings that need writing down
but not a record each.

## Context

### Rate limiting bounds frequency, not work

Both existing tiers ([0009](0009-in-process-rate-limiting.md),
[0016](0016-second-tier-rate-limiting-and-honeypot.md)) count requests per
client. Neither bounds how many are being served **at the same time**, and a
submission is unusually expensive to serve: two SMTP connections and a Sheets
write, each with its own timeout.

The worst case is the sum of those timeouts, and the host's own numbers say what
that costs. From [../hosting.md](../hosting.md#watch-worker-memory):

| Figure                | Value                                      |
| --------------------- | ------------------------------------------ |
| Worker footprint      | 80–115MB PSS under load                    |
| LVE physical memory   | 3GB, ~0.5GB observed, **zero faults** ever |
| LVE process cap       | 300, ~10 observed                          |
| Worst-case submission | ~35s (10s + 10s SMTP, 15s Sheets)          |

So memory is the binding constraint, not the process cap: roughly **30
concurrent workers reaches 3GB**, and Passenger spawns them per request without
capping them.

**The attack is now expensive, and that is worth stating plainly.** After 0017,
a browser-driven flood is refused on `Origin`, so this needs a scripted caller
sending none — and those are bounded at 10/hour each. Holding 30 workers for an
hour needs 108,000 worker-seconds against 350 per address, so roughly **309
distinct IPs**. That is a real bar, and on its own it would not justify new
machinery.

**The likelier trigger is not an attacker at all.** Every one of those 35
seconds is spent waiting on SMTP or Sheets. When the mail server is slow rather
than down — the failure mode `/health/deep` exists for, and the one that
actually happened on 2026-07-30 — _legitimate_ submissions each hold a worker
for the full timeout. Ordinary traffic then piles up against the memory cap
without anyone attacking anything, and the first symptom is an LVE fault taking
out the whole account, static site included.

### Three smaller findings

- **Nothing had ever confirmed `remote_addr` is the caller.** Every per-IP
  control assumes it, 0014 reasoned carefully about which header to trust, and
  the assumption was never checked against the deployed app. If it resolved to
  something in front of the app, all of it would be one shared bucket and a
  single caller could exhaust everyone's allowance. New Relic cannot answer it:
  the agent records a fixed header allowlist that does not include any client
  address.
- **The confirmation greeting is caller-chosen text in a signed email.** The
  campaign's domain publishes `p=reject` DMARC with strict alignment, so mail it
  sends authenticates. The greeting took up to 80 characters verbatim into the
  plain-text part — enough to put "CALL 555-0142 NOW" at the top of a message
  from Julia to a stranger, since the recipient is also caller-chosen.
- **The API sends none of the site's security headers.** The apex sends HSTS
  with `includeSubDomains`, but that only protects a browser that has already
  been to the apex.

## Decision

**1. Cap concurrent submissions at 12** (`MAX_CONCURRENT_SUBMISSIONS`), counted
in the SQLite store 0016 already introduced, refusing the overflow with `503`
and a short `Retry-After`.

Twelve sits well under the ~30 that would threaten the memory cap, and well
above the ~10 processes the whole account was observed using. It is a ceiling on
the pathological case, not a throttle on the normal one — a municipal campaign
does not have twelve people submitting forms in the same 35 seconds.

**In SQLite, for the reason 0016 gave.** Passenger reaps idle workers, so
process memory cannot hold state that has to be shared _between_ workers, and
"how many submissions are in flight" is exactly that. An in-process counter here
would read 0 or 1 forever and bound nothing.

**Slots expire.** A worker killed mid-request never reaches its `release`, and
without a TTL those slots would accumulate until the cap was permanently full
and every submission returned 503 — an outage of our own making that a restart
would not clear, because the count is on disk.

**The TTL is derived, not chosen** (270s by default), and the arithmetic behind
it is the part worth knowing. `SMTP_TIMEOUT_SECONDS` bounds each blocking socket
operation, **not the session** — and one send is a dozen or so operations
(connect, banner, EHLO, STARTTLS, EHLO, AUTH, MAIL, RCPT, DATA, body, QUIT), so
a server answering every command just inside the timeout drags a submission out
to that multiple of it. The first version of this record put the worst case at
35s by summing the timeouts once; Copilot pointed out on PR #138 that this is
short by an order of magnitude, and that a slot reclaimed while its request is
still running admits callers _above_ the cap in exactly the slow-upstream
conditions the cap exists for. Expiring late is the cheaper mistake — it only
delays reclaiming a slot after a crash — so the bound is deliberately
pessimistic, and the test checks it against the **configured** timeouts rather
than the default constants.

**`/health/deep` gets its own budget** (`MAX_CONCURRENT_HEALTH_PROBES`, 2),
counted under a separate scope. Also from Copilot's review: the cap as first
written covered submissions only, while the probe does the same expensive I/O on
a cache miss under a _larger_ per-client allowance (30/hour against the forms' 10) — an uncapped path to the exhaustion the cap exists to prevent, and a
cheaper one per address than the forms. Separate scopes mean neither kind of
work can spend the other's allowance. When every probe slot is busy and a
cached result exists, that result is served with an honest `Age` rather than a
refusal: a stale answer is worth more to a monitor than a 503, which would page
as though a dependency had broken.

**It fails open**, like the tier beside it. A store that cannot be reached
admits the request.

**2. `/health` echoes the key the limiter derives.** The endpoint already
returns `path` and `script_root` to answer "what does the deployed app see"; the
client key is the same kind of question and had a sharper consequence. A caller
only ever learns their own address.

**3. The confirmation greeting is filtered to letters, spaces, apostrophes and
hyphens, and truncated to 30 characters.** `str.isalpha()` rather than an ASCII
pattern, so accented and non-Latin names pass unharmed. No `.`, because that is
what lets a domain survive and some mail clients linkify one. **Only the
greeting** — the notification to the campaign and the sheet row keep the
submitted value verbatim, because those are what a volunteer follows up on.

**4. The API sets `Strict-Transport-Security` and `X-Content-Type-Options`**
from an `after_request` hook rather than an `.htaccess`, against
[0010](0010-edge-policy-in-htaccess.md)'s general rule. The API subdomain's
docroot is not in this repo, so a header added there is untracked host state
that no test and no deploy can see; in the app it is both.

**5. `security.txt` ships at the docroot** and is rewritten to the canonical
`/.well-known/security.txt`, because the deploy's `dist/**` scp glob does not
match dotfiles — the same reason `.htaccess` needs its own upload step. A
dot-directory would build locally and never leave the runner.

## Consequences

- **A 503 counts against the API error-rate alert**, which is intended: the site
  shedding submissions is worth a page. The log line names the cap, so the
  alert is distinguishable from a genuine fault at a glance.
- **The cap is global, not per client.** One caller filling all twelve slots
  turns away everyone, which is the correct trade at this ceiling — the
  alternative is the memory cap taking out the whole account rather than one
  form — but it does mean the cap is a blunter instrument than the rate limiter
  and belongs above it, not instead of it.
- **Two more SQLite writes per submission**, on a path that already spends
  seconds on the network. Both are single-row operations on a WAL database in
  the app's own `tmp/`.
- **`INFLIGHT_TTL_SECONDS` and the SMTP/Sheets timeouts are now coupled.** They
  were independent knobs; the TTL has to clear their sum. The test says so when
  it stops being true.
- **A name that is entirely digits or punctuation now greets as "there".** That
  is the intended trade, and it is why the sanitiser keeps Unicode letters
  **and combining marks** rather than matching an ASCII name pattern. Marks are
  not decoration: `str.isalpha()` is false for one, so the first version of this
  filter turned decomposed "José" into "Jose" and "अनुराधा" into "अनरध", which is
  not a spelling of anything. Copilot caught it on PR #138; the original test
  passed only because Python source literals are NFC by default.
- **`inflight` gained a `scope` column after shipping to the test host.** The
  file lives under `tmp/`, which the deploy's prune step leaves alone, so
  `CREATE TABLE IF NOT EXISTS` would have found the old table and left it — and
  every insert would then have failed, failing open forever and silently. There
  is now a guarded `ALTER TABLE` in `_connect`, which is this repo's first
  schema migration and the pattern for the next one.

## Alternatives considered

- **Shorten the worst case instead of bounding concurrency.** Tightening the
  timeouts, or making the sheet append non-blocking, reduces how long a worker
  is held rather than how many are held. It is genuinely simpler, but it trades
  away the recovery ordering [0004](0004-no-database.md) depends on — the append
  runs after the mail is away precisely so a failure there is recoverable — and
  a slow upstream still piles workers up, just fewer deep. Worth revisiting
  together with a queue if this campaign ever has the traffic to need one.
- **Cap Passenger's pool at the host instead.** The honest ceiling, and it needs
  no code. Rejected as the _only_ control because it is cPanel state with no
  representation in the repo (the same objection as the API's headers above),
  and because being refused by Passenger is a 500-class failure to the
  submitter, where this is a `503` with `Retry-After` and a message. The two are
  complementary; if the pool ever gets capped, this stays useful.
- **A per-client concurrency cap.** Bounds the attacker without turning anyone
  else away, but does nothing for the upstream-slowdown case, where every holder
  is a different legitimate person. That case is the reason this record exists.
- **Rejecting a `null` or absent `Origin` on `/health`.** Considered while adding
  the client echo, and dropped: the endpoint is deliberately reachable by
  anything, and the value it returns is already the caller's own.
