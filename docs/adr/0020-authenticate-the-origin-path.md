# 0020. Authenticate the edge-to-origin path with a shared secret

**Status:** Accepted
**Date:** 2026-08-16

Amends [0019](0019-cloudflare-in-front.md), which proxied the web hostnames and
left the origin directly reachable, and closes
[#141](https://github.com/OwlbearMedia/voteforjulia/issues/141).

0019's consequence stands unchanged: the origin is reachable without passing the
edge. What changes is how that gets closed. #141 proposed restricting the origin
to Cloudflare's published IP ranges. **That fix does not work on this host, and
would have caused the outage it was written to avoid.** The measurement is the
substance of this record.

## Context

`mail.voteforjulia.com` cannot be proxied — Cloudflare does not carry SMTP — so
the MX record publishes `208.115.234.114` to anyone who queries DNS. Confirmed
still open on 2026-08-16, with matching SNI rather than a `Host:` header:

```
curl --resolve voteforjulia.com:443:208.115.234.114 https://voteforjulia.com/
  → 200, server: LiteSpeed, no cf-ray

curl --resolve api.voteforjulia.com:443:208.115.234.114 https://api.voteforjulia.com/health
  → 200, server: LiteSpeed, no cf-ray
```

Both entry points, edge bypassed.

### Why the IP allowlist is the wrong instrument here

**The origin never sees Cloudflare's address.** The host restores the real client
address before anything at the origin reads it — 0019 recorded that from the
access log and drew only the logging conclusion from it. The access-control
consequence is the one that matters, and it inverts the fix.

Measured against a throwaway directory on the test docroot, 2026-08-16:

| `.htaccess` rule            | via Cloudflare | direct to IP |
| --------------------------- | -------------- | ------------ |
| `Require ip <CF ranges>`    | 200            | 200          |
| `deny from all`             | 403            | 403          |
| `Allow from <our own addr>` | **200**        | 200          |
| `Allow from <CF ranges>`    | **403**        | 403          |

Two independent findings, either of which sinks the proposal:

- **`Require ip` is silently ignored on this host.** Row 1 refuses nothing, in
  either direction. Only the `mod_access_compat` spelling (`Order`/`Allow`/
  `Deny`) enforces, which is why cPanel's IP Blocker writes `deny from`. A
  `Require`-based allowlist would have looked like a closed door and been a no-op
  — the worst of the available failures, because nothing about it reads as
  broken.
- **Access control evaluates the restored visitor address.** Row 3 allows our own
  address and succeeds _through the proxy_; row 4 allows Cloudflare's ranges and
  is refused _through the proxy_. So the allowlist #141 describes denies 100% of
  real traffic on the deploy that ships it.

#141's first care point was that a stale range list takes the site down silently.
The list would not have had to go stale. It would have done that immediately.

### Two more constraints the instrument has to satisfy

- **`mail.voteforjulia.com` serves the whole site from `public_html`.** Not just
  incidental static files — the homepage, `/donate`, the real `<title>`, on a
  grey-clouded hostname that resolves straight to the origin. So `mail` is not a
  hostname to exempt; it is a second front door. **Scoping this control by `Host`
  is what reopens it** — the first version of this decision did exactly that, and
  the bypass survived as `https://mail.voteforjulia.com/`, reachable by changing
  one word in the URL. Found in review, after the ADR already claimed the bypass
  was closed. The control is therefore scoped by **path**, exempting only what a
  mail client needs.
- **The API docroot is outside this repo's reach.** `api-sub/.htaccess` and
  `api_test/.htaccess` carry the CloudLinux Passenger config and every `SetEnv`,
  and both deploy workflows explicitly protect them from the prune. Nothing here
  deploys them. A `public/.htaccess` control therefore covers the frontend and
  leaves `api.voteforjulia.com` — the endpoint the spam bot actually posts to —
  open. That is [0018](0018-cap-concurrent-submissions.md)'s mistake repeated,
  and it is structural here rather than an oversight.

## Decision

**Cloudflare stamps every proxied request with a shared secret header, and the
origin refuses requests that do not carry it.** No IP list is involved, so
nothing about this can go stale.

A Transform Rule at the edge sets `X-Origin-Token: <secret>` on every request.
The secret lives in a GitHub Actions secret, is substituted into the built
`.htaccess` by [scripts/arm-edge-gate.sh](../../scripts/arm-edge-gate.sh) on the
runner during the deploy job, and is set on the cPanel app as
`EDGE_SHARED_TOKEN`. **It is never committed** — this repo is public.

**Production and test get different tokens**, with a Transform Rule each, matched
on hostname. Sharing one was the first version of this decision and was wrong:
the test pipeline deploys PR-head code into `api_test` and a PR-built
`.htaccess` into the test docroot, so a shared value is readable by any branch
someone can push — `os.environ["EDGE_SHARED_TOKEN"]` from a deployed route is
enough — and that value would authenticate direct requests to **production**.
Found in review. The cost is a second rule to keep scoped correctly, and the
hostname trap below now has two ways to go wrong instead of one.

Enforcement covers every entry point that shares the property, named explicitly
because the sibling-path hole is the easy mistake:

| Entry point                              | Covered by                   | Notes                                |
| ---------------------------------------- | ---------------------------- | ------------------------------------ |
| `voteforjulia.com`, `www` (all paths)    | `public/.htaccess`           | path-scoped rewrite, `[F]`           |
| `test.voteforjulia.com`                  | same file, same rule         | its own token; see above             |
| **`mail.voteforjulia.com`** (site paths) | same file, same rule         | serves the whole site; the bypass    |
| `api.voteforjulia.com` `/send-email`     | `before_request` in `app.py` | covers the method, not the route     |
| `api.voteforjulia.com` `/yard-sign`      | same hook                    |                                      |
| `api.voteforjulia.com` `/health`         | same hook                    |                                      |
| `api.voteforjulia.com` `/health/deep`    | same hook                    | the path 0018's cap was left off     |
| `test-api.voteforjulia.com` (all)        | same hook                    |                                      |
| `/.well-known/` on any hostname          | **deliberately excepted**    | AutoSSL; see below                   |
| `/autodiscover/` on any hostname         | **deliberately excepted**    | mail-client setup                    |
| `autoconfig.voteforjulia.com`            | not reached                  | cPanel answers it before the docroot |
| `cpanel`, `webmail`, `webdisk`, `ftp`    | out of scope                 | separate ports, not this docroot     |

The API hook is a `before_request` rather than a per-route check, so a route
added later is covered without anyone remembering to cover it.

Two paths are excepted on purpose, and both are narrow enough to be worth it.
`/.well-known/` carries AutoSSL's domain-control validation, and a failed
renewal is a certificate expiry — a worse outage than the path it reopens, which
serves only ACME challenges and `security.txt`. `/autodiscover/` is how mail
clients configure themselves, and it is matched as `[Aa]utodiscover` rather than
with `[NC]`: **that flag breaks a negated `RewriteCond` on LiteSpeed**, failing
closed and refusing Outlook. Measured, like everything else here; recorded in
[hosting.md](../hosting.md#nc-breaks-a-negated-rewritecond).

**Both enforcement points fail open until explicitly switched on.** The API reads
`EDGE_TOKEN_ENFORCED`, defaulting to **false**, matching the kill-switch
convention of [0016](0016-second-tier-rate-limiting-and-honeypot.md)'s honeypot
and [0017](0017-origin-trust-boundary-and-health-probe-cache.md)'s origin check.
With no token configured it does nothing at all. The ordering that matters:
create the Transform Rule, confirm the header arrives, then enforce.

## Consequences

- **The bypass closes for every hostname served from these two docroots**, which
  is what #141 asked for, without a range list to refresh. The failure mode #141
  spent most of its length on does not exist in this design.
- **`mail.voteforjulia.com` stops serving the site**, which is a behaviour change
  rather than a pure hardening: it returns 403 for site paths instead of a
  working copy of the homepage. Nothing links to it and it was never an intended
  entry point, but a bookmark to it will break.
- **The deploy support has to merge before the gate does**, in a separate change.
  `workflow_run` runs `main`'s copy of a workflow
  ([hosting.md](../hosting.md#deploy-workflow-changes-cannot-be-tested-from-a-pr)),
  so a branch adding the substitution step and the `.htaccess` block together is
  deployed by a `main` that cannot substitute: the placeholder reaches the
  docroot literally and refuses every visitor. That is precisely the outage the
  unset-secret branch exists to prevent, arriving by the one route that branch
  cannot cover. Observed rather than predicted — the first attempt took the test
  site to 403 on every path. The order is substitution, then the gate, then the
  secret: the substitution step refuses to run against a build with no
  placeholder in it, so arming the secret in between fails the deploy.
- **The secret is deployment state with no representation in the checkout**, like
  the cPanel environment variables in [hosting.md](../hosting.md#environment-variables).
  Each of the two tokens lives in three places that must agree: its Cloudflare
  Transform Rule, its GitHub Actions secret, and `EDGE_SHARED_TOKEN` on its
  cPanel app.
- **Rotation cannot be done in place, and is an outage if attempted that way.**
  The frontend compares against exactly one value baked into `.htaccess` at
  deploy time, so from the moment the Transform Rule changes until a full CI run
  and deploy agree with it, every proxied request to the site is refused. No
  ordering avoids this — changing the API last only protects the side that fails
  open anyway, while the frontend is the side that goes down. Rotation therefore
  disarms both ends first and re-arms them after, trading a few minutes of open
  origin for not taking the site down; the sequence is in
  [hosting.md](../hosting.md#rotating-the-token). This is the cost of the design
  and the strongest argument for the mTLS alternative below.
- **A fourth drift surface.** The Transform Rule lives only in Cloudflare's
  dashboard, alongside the firewall rules and the monitors. Nothing syncs it and
  nothing warns if it is edited away — the symptom would be the whole site
  returning 403.
- **A refused submission is unrecoverable, unlike every other failure path.**
  The hook runs before the body is parsed, so a 403 here logs the path and
  nothing else — where `_log_request_body` otherwise preserves a lost
  submission well enough to follow up with the person by hand, which has been
  used in practice. The case to watch is a token rotated on the API but not at
  the edge: the site serves normally and only the forms refuse.
  **`/health` is what saves this** — the hook covers it, so that state fails the
  synthetic monitor instead of going quiet, which is the opposite of the
  `$`-in-env-var trap in [hosting.md](../hosting.md#app-env-vars-must-not-contain-)
  that takes SMTP down while `/health` stays green. Pinned by
  `test_every_route_refuses_an_unproxied_caller`.
- **This is authentication, not authorisation of the visitor.** Anyone who learns
  the token can bypass the edge again. It defends against a scanner that read the
  MX record, which is the actual threat; it does not defend against someone who
  has read the deploy logs or the cPanel environment.
- **The token has to cross the deploy's SSH transport, which was never
  verified.** It cannot be avoided: `.htaccess` cannot read an environment
  variable, so the value has to reach the file on the host. Substitution happens
  on the runner — ephemeral, single-tenant, destroyed with the job — so what
  crosses is the armed `.htaccess`, and that upload is the first thing either
  workflow sends carrying a secret. It runs in the deploy job rather than the
  build job because the build job's output is an artifact, and an artifact is
  downloadable. `appleboy`'s actions skip host-key verification when no
  fingerprint is given, so the deploy now pins one and refuses to upload with a
  token configured and no fingerprint. The other sixteen SSH and SCP steps remain
  unpinned — they carry no secret, but they do carry what gets deployed, so the
  exposure there is integrity rather than disclosure, and pinning them all would
  put a total deploy outage one host-key rotation away. Tracked as
  [#148](https://github.com/OwlbearMedia/voteforjulia/issues/148).
- **Guessing the token is the whole attack, and the origin meters nothing.**
  Carrying the header is the only thing checked, and a caller refused here never
  reached the edge, so the 403 answers guesses as fast as the origin will serve
  them. That makes the token's entropy the control, not the check around it: the
  deploy enforces at least 32 alphanumeric characters and
  [hosting.md](../hosting.md#closing-the-direct-to-origin-path) gives the
  generation command, because the realistic failure is a value someone chose to
  be memorable rather than one deliberately made short.
- **`Require` directives cannot be trusted on this host at all.** The finding
  generalises past this decision: anything written in `mod_authz_core` spelling
  is a silent no-op here. Recorded in
  [hosting.md](../hosting.md#require-is-silently-ignored) because the next person
  to reach for an access rule will reach for the modern one.
- **A local `curl` of the origin no longer resembles production.** Debugging
  against `--resolve` now needs the header, or it returns 403 and looks like a
  different fault.
- **Cloudflare rewrites `robots.txt` at the edge**, discovered while proving the
  shared docroot. `public/robots.txt` is 70 bytes; the apex serves Cloudflare's
  Content Signals preamble instead. Unrelated to this decision and left alone
  here, but it means a tracked file's served bytes are not ours.

## Alternatives considered

- **Cloudflare IP range allowlist**, as #141 proposed. Measured above: silently
  ignored in `Require` form, and a total outage in `Allow from` form. The
  underlying reason — the host restores the client address before access control
  — is not something a different spelling can work around.
- **Authenticated Origin Pulls (mTLS).** Cloudflare's own answer to this problem
  and strictly stronger, since the credential cannot leak through a deploy log.
  It needs the origin to verify a client certificate, which is web-server
  configuration we do not have on shared cPanel hosting.
- **Accepting an old and a new token during an overlap**, which would make
  rotation orderless and remove the outage window above. It needs a second
  placeholder in `.htaccess`, a second repository secret, and a second value
  parsed on the API side — permanent complexity in the enforcement path, on
  every request, to smooth an operation that has not yet been performed once.
  Deferred rather than rejected: the trigger for revisiting is a rotation that
  actually has to happen under time pressure, such as a leaked token.
- **A host-level firewall allowlist.** Operates on the true TCP peer, so the IP
  restoration does not defeat it, and it would cover every docroot and every port
  at once. Not self-service on shared hosting, and it is the option that can lock
  us out of the control panel needed to undo it. Worth revisiting only if the
  token proves insufficient.
- **Accept the gap.** What 0019 chose, and defensible while the only observed
  attacker targets the hostname. Rejected now because the `deny from` removal on
  2026-08-15 left the address strictly less defended than the hostname, and
  because a scanner reading MX records is ordinary background internet traffic
  rather than a hypothetical.
