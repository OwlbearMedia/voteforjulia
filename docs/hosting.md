# Hosting and deploys

What the code runs on, and the parts of it you cannot infer from the repo.

## The web server is LiteSpeed, not Apache

```
$ curl -sI https://voteforjulia.com/ | grep -i '^server:'
server: LiteSpeed
```

Shared cPanel-style hosting. LiteSpeed reads [public/.htaccess](../public/.htaccess)
with Apache-compatible directives, **but its config parser is not identical to
Apache's**, and the differences are silent — a mis-parsed directive produces a
malformed header rather than an error.

The one that has already bitten us:

| Form                     | Apache        | LiteSpeed                      |
| ------------------------ | ------------- | ------------------------------ |
| `Header set X "a \"b\""` | emits `a "b"` | emits `a \"b\"` (backslashes!) |
| `Header set X 'a "b"'`   | emits `a "b"` | emits `a "b"`                  |

**Never use backslash escapes in `.htaccess`.** When a header value needs
embedded double quotes, delimit the argument with single quotes.

### `Require` is silently ignored

The same parser difference reaches access control, and this one has no visible
symptom at all. **`Require` directives — the `mod_authz_core` spelling every
current Apache document recommends — do nothing on this host.** The old
`mod_access_compat` spelling is what enforces, which is why cPanel's IP Blocker
writes `deny from`.

Measured 2026-08-16 against a throwaway directory on the test docroot:

| Rule                                | Result                        |
| ----------------------------------- | ----------------------------- |
| `Require ip <some range>`           | **not enforced** — serves 200 |
| `Require all denied`                | **not enforced** — serves 200 |
| `deny from all`                     | 403                           |
| `Order allow,deny` + `Allow from …` | enforced                      |

A `Require` rule fails open and looks correct in the file, so nothing about it
reads as broken — the review passes, the deploy succeeds, and the door is open.
Write access rules in the `Order`/`Allow`/`Deny` form, or use a `RewriteRule`
with `[F]`, and verify against the deployed site rather than locally.

### Reaching the host

Every `ssh vfj` / `scp … vfj:` command on this page assumes a `vfj` host alias in
your `~/.ssh/config`, so the hostname, port, user and key live in one place
rather than being pasted around:

```
Host vfj
    HostName <host>
    Port <port>
    User <cpanel-user>
    IdentityFile ~/.ssh/<key>
```

The four values are the same ones held as the `SSH_HOST`, `SSH_PORT`,
`SSH_USERNAME` and `SSH_PRIVATE_KEY` repository secrets. `ssh -G vfj` prints what
the alias resolves to without connecting, which is the quickest way to confirm it
is set up and the source of the host and port in the fingerprint step below.

#### Probing an `.htaccess` question safely

Nothing about this host's parser can be settled by reading documentation, and a
rule under test does not need to be tested on the live docroot. Put it in a
throwaway subdirectory instead — `.htaccess` applies per-directory, so the blast
radius is one path nothing links to:

```
ssh vfj 'mkdir -p ~/public_html_test/probe && echo ok > ~/public_html_test/probe/index.html'
scp rule.htaccess vfj:public_html_test/probe/.htaccess
curl -so /dev/null -w '%{http_code}\n' https://test.voteforjulia.com/probe/
curl -so /dev/null -w '%{http_code}\n' \
  --resolve test.voteforjulia.com:443:208.115.234.114 https://test.voteforjulia.com/probe/
ssh vfj 'rm -rf ~/public_html_test/probe'
```

The two `curl`s are the pair worth running every time: through the edge, and
direct to the origin. Two traps, both of which produce a confident wrong answer:

- **`%{REQUEST_URI}` is the full path**, so a docroot-shaped condition like
  `!^/\.well-known/` never matches inside `/probe/`. Re-scope the condition to
  the probe path, or the exception looks broken when it is fine.
- **`mail.` falls through to the _production_ docroot**, not the test one, so a
  probe under `public_html_test` is invisible to it and answers 404. Test
  host-scoping by inverting it — scope the rule to a host you are not sending —
  rather than by trying to reach the probe as `mail.`.

Use `--resolve`, never a `Host:` header against the IP: the mismatched SNI
serves a different vhost and reports a misleading result.

### `[NC]` breaks a negated `RewriteCond`

Measured 2026-08-16, on the same probe. A negated condition with the
case-insensitive flag stops excluding what it names, and the rule it guards
fires anyway:

| Condition                                          | Exempts the path? |
| -------------------------------------------------- | ----------------- |
| `RewriteCond %{REQUEST_URI} !^/autodiscover/`      | yes               |
| `RewriteCond %{REQUEST_URI} !^/autodiscover/ [NC]` | **no**            |

It fails **closed**, which is the dangerous direction for an exemption — the
path you meant to let through gets refused. Use a character class instead
(`!^/[Aa]utodiscover/`) and do not "tidy" it back to `[NC]`. This is why
[public/.htaccess](../public/.htaccess) spells the autodiscover exemption that
way. The autodiscover path is the example rather than the stake — cPanel
answers the canonical one above the docroot — but the flag is general, so any
negated condition written with it excludes nothing.

### Access control sees the visitor's address, not Cloudflare's

The host restores the real client address before anything at the origin reads
it — logging and access control alike. Consequences, both counter-intuitive:

- A `deny from <address>` still refuses that visitor while proxied. The cPanel
  blocklist is a real second layer, not dead weight.
- **An allowlist of Cloudflare's IP ranges refuses everyone**, including
  Cloudflare. Measured: `Allow from <our own address>` succeeds _through the
  proxy_, `Allow from <Cloudflare's ranges>` is refused through it. This is why
  [ADR-0020](adr/0020-authenticate-the-origin-path.md) authenticates the edge
  with a shared secret instead, and why [#141](https://github.com/OwlbearMedia/voteforjulia/issues/141)'s
  original proposal would have taken the site down.

### App env vars must not contain `$`

The same parser handles the `SetEnv` lines cPanel generates for the Python apps'
environment variables — and **cPanel writes those values unquoted**, so LiteSpeed
interpolates `$name` as a variable and expands it to nothing.

This cost real downtime on 2026-07-30. A rotated `EMAIL_PASSWORD` containing a
`$` reached the app three characters shorter than it was stored, and every form
submission failed with `SMTPAuthenticationError (535, 'Incorrect authentication
data')` while the stored value authenticated fine when tested directly. It hits
both apps at once, so production forms break silently — `/health` does not
exercise SMTP, so nothing goes red.

**Choose app env var values from `[A-Za-z0-9._~-]`.** Avoid `$`, `{`, `}`, `"`,
`\`, backtick, and spaces. Hand-quoting the generated file is not a fix; cPanel
rewrites it. The variables this applies to are listed under
[Environment variables](#environment-variables); `EMAIL_PASSWORD` and
`GOOGLE_SERVICE_ACCOUNT_JSON` are the two where a stray `$` is most likely.

To confirm what a running worker actually received, compare it against the stored
config — hash the values, never print them:

```
python -c 'import os,hashlib; print(hashlib.sha256(os.environ["EMAIL_PASSWORD"].encode()).hexdigest()[:12], len(os.environ["EMAIL_PASSWORD"]))'
```

Run that inside the app's virtualenv, and read `/proc/<lswsgi-pid>/environ` for
what the live process holds. A length mismatch against the value in the selector
config is the signature.

### Changing a response header

Because local Apache is not a faithful proxy for the host, never sign off on a
header change by testing locally. The loop is:

1. Edit [public/.htaccess](../public/.htaccess) (it is copied verbatim into `dist/`).
2. Open a PR — that deploys to the test environment (see below).
3. Check the bytes actually served:

   ```
   curl -sI https://test.voteforjulia.com/donate | grep -i permissions-policy
   ```

4. Only then merge.

A local Apache run is still useful for catching outright syntax errors before
you push, and it will confirm the _intended_ value, but it cannot tell you what
LiteSpeed will emit.

## Imunify360 WAF (disabled)

**The host disabled Imunify360 on 2026-08-01**, at our request, after it made the
Cypress suite unrunnable — and **not for the whole account, which this page
claimed until 2026-08-15.** The exclusion covered `test.voteforjulia.com` only.
`test-api.voteforjulia.com` was never in it, and WebShield went on challenging
GitHub's runners there for two weeks, failing the e2e suite intermittently and
passing on a re-run whenever a different runner address was drawn. The host
disabled it for the remaining hostnames on 2026-08-15.

**Ask which hostnames an exclusion covers, not whether one exists.** A per-host
exclusion and an account-wide one look identical from the one hostname you
happened to test.

Kept here because it is not gone, only switched off — a host-side setting we do
not control, on an account where it was on by default. If the symptoms below
reappear, this is the cause, and the remedy is another support request rather
than a code change. It also explains a long run of "impossible" intermittent CI
failures in the history.

Everything from here down describes how it behaved **while it was on**.

---

The host runs CloudLinux (the API deploy drives `cloudlinux-selector`), and with
it Imunify360, as an **openresty reverse proxy in front of LiteSpeed**. It was
invisible until it decided to challenge a visitor: normally it passed requests
through untouched, `Server: LiteSpeed` and all. When it did challenge, it
answered **every URL on the domain** itself, and the response looked nothing like
ours:

| Signal    | Normal           | Challenged                    |
| --------- | ---------------- | ----------------------------- |
| `server:` | `LiteSpeed`      | `openresty/<version>`         |
| `<title>` | the page's title | `One moment, please...`       |
| Body      | ~40 kB prerender | ~12 kB verification splash    |
| Status    | 200              | 200 — it is not an error page |

The splash reads _"Please wait while your request is being verified…"_ under a
green starburst.

The challenge page's only content is
`setTimeout(() => window.location.reload(), 5000)`, plus a script that
fingerprints the browser and reports the result to a callback URL. **Nothing
about it is visible in a status code**; a monitor that checks for HTTP 200 sees
a healthy site.

Two consequences worth knowing before debugging anything that "the site is
broken from over there":

- **It is triggered by source IP reputation**, not by the request. The same URL
  serves fine from one network and is challenged from another, at the same
  moment, which reads as an impossible intermittent fault.
- **A browser that fails the fingerprint can never get past it.** The callback
  carries the failed checks as query parameters (`failedChecks=webdriverCheck`,
  `userAgentCheck`, `appVersionCheck`), and on a failure it simply re-serves the
  splash — so the client reloads the same URL every 5 seconds forever. This is
  what breaks the Cypress suite; see
  [conventions.md](conventions.md#testing).

The remedy was host-side — the account's Imunify360 settings, or a support
request to exclude the domain, which is what was eventually done. Runner or
visitor IPs could not be whitelisted: GitHub's are dynamic Azure ranges, and
real visitors on VPNs and mobile CGNAT get flagged the same way. The same WAF
fronted the production domain, where an unresolvable loop landed on `/donate`.

### Checking whether it is back

`Server: LiteSpeed` on a normal request proves nothing — it said that while the
WAF was on too, right up until it decided to challenge. The tells are
`server: openresty`, a ~12 kB body where a ~40 kB prerender belongs, or
`One moment, please...` as the title:

```
curl -sI https://voteforjulia.com/ | grep -i '^server:'
```

The reliable signal is a **failure that varies by source IP** — one CI runner or
one synthetic location failing while others pass. See
[monitoring.md](monitoring.md#is-it-real), which uses exactly that split to tell
a WAF challenge from a real outage.

## Migrating DNS to Cloudflare

Why, and what it does and does not buy, is
[ADR-0019](adr/0019-cloudflare-in-front.md). **Done on 2026-08-15** — every web
hostname is proxied, `mail` is not. The sequence below is what was executed, kept
because it is also the sequence for the next zone and because the verification
steps are the ones to re-run whenever anything about the edge changes.

The order matters more than any individual step. Two of them can break the site
for real visitors, and neither fails loudly.

**Verified after the cutover**, all against production:

| Check                                         | Result                                               |
| --------------------------------------------- | ---------------------------------------------------- |
| `/health` reports the visitor, not Cloudflare | real address — `TRUSTED_CLIENT_IP_HEADER` live       |
| Mail authenticates                            | `spf=pass dkim=pass dmarc=pass` under `p=reject`     |
| Origin access log identifies visitors         | yes — **0** Cloudflare-range client addresses        |
| Cypress against the proxied test zone         | clean run, baseline probe `answered by our API: yes` |
| CSP violations                                | none; the Web Analytics beacon is off                |

### Before touching DNS

**Set `TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP` on both cPanel apps and
restart them.** Do this first, while the site is still direct. It is read at
import, so it needs a Passenger restart, and until it is in place a proxied site
sees every visitor as a Cloudflare address — one shared rate-limit bucket, and
0009's five-per-sixty-seconds starts refusing real supporters.

Setting it early does mean the header is briefly forgeable, which is what
[ADR-0014](adr/0014-do-not-trust-forwarding-headers.md) warns about. That is the
right way round: the cost is a limiter the bot could bypass — which it already
bypasses by rotating addresses — against the alternative of turning away
volunteers.

Record what the client address looks like now, because this is the check that
catches the failure:

```
curl -s https://api.voteforjulia.com/health | jq -r .client   # your address
curl -s https://api.ipify.org                                 # must match
```

### The sequence

1. **Add the domain in Cloudflare, let it import DNS, then diff the import
   against cPanel → Zone Editor by hand.**

   **Cloudflare's importer guesses.** It cannot do a zone transfer, so it probes
   common labels and imports whatever answers. On this zone it missed
   `test-api`, which is a real A record. Anything it misses simply stops
   resolving when the nameservers change, and nothing warns you.

   The records that must be present afterwards, and how they should be set:

   | Record                                | Type    | Proxy    |
   | ------------------------------------- | ------- | -------- |
   | `voteforjulia.com`                    | A       | orange   |
   | `www`                                 | A/CNAME | orange   |
   | `api`, `test`, `test-api`             | A       | orange   |
   | `mail`                                | A       | **grey** |
   | `cpanel`, `webmail`, `webdisk`, `ftp` | A       | **grey** |
   | `autodiscover`, `autoconfig`          | A       | **grey** |
   | `@` → `mail`                          | MX      | n/a      |
   | SPF (`v=spf1 …`)                      | TXT     | n/a      |
   | DKIM (`default._domainkey`)           | TXT     | n/a      |
   | DMARC (`_dmarc`)                      | TXT     | n/a      |

   Confirm each one resolves the same before and after. This snapshot is the
   before:

   ```
   for h in "" www. api. test. test-api. mail. cpanel. webmail. webdisk. ftp. autodiscover. autoconfig.; do
     printf '%-16s %s\n' "$h" "$(dig +short A ${h}voteforjulia.com | head -1)"
   done
   dig +short MX voteforjulia.com
   dig +short TXT voteforjulia.com | grep -i spf
   dig +short TXT default._domainkey.voteforjulia.com
   dig +short TXT _dmarc.voteforjulia.com
   ```

   **The mail records are the ones to be paranoid about.** DMARC is published as
   `p=reject` with strict alignment, so a lost or altered SPF/DKIM/MX record does
   not send mail to spam — receivers refuse it. Every form on the site emails
   somebody, so that is a silent outage of the site's whole purpose.

2. **Grey-cloud `mail.voteforjulia.com`.** Cloudflare proxies HTTP(S) only, so
   an orange cloud on that record breaks SMTP on 465, which breaks every form on
   the site. `/health` stays green throughout, so nothing tells you.
3. **Orange-cloud `test` and `test-api` only.** Leave production grey.
4. **Change nameservers at the registrar.** This is the slow, hard-to-reverse
   step; do it when you can watch. Everything is still direct except test.
5. **Verify against test** (below). Do not proceed until all four pass.
6. **Orange-cloud production**: root, `www`, `api`.
7. **Verify against production**, same four checks.
8. **Add the IP blocks to Cloudflare.** Then decide, deliberately, what to do
   with the `deny from` lines — the reasoning is not what it looks like.

   An earlier draft said to delete them because Apache would only ever see
   Cloudflare's addresses once proxied. **That is not what happens here**: the
   host restores the real client address, so `.htaccess` still matches and those
   rules still enforce. Measured after the cutover — zero Cloudflare-range
   client addresses in the origin's access log.

   So they are a real second layer, not dead weight. **They were removed anyway
   on 2026-08-15**, on the grounds that Cloudflare covers every caller who
   targets a hostname, while a growing origin blocklist carries its own failure
   mode: addresses get reassigned, and a stale `deny` refuses a real supporter
   silently and with no diagnostic.

   What that trades away is direct-to-address traffic, which Cloudflare cannot
   see. Nothing has ever arrived that way here — the spammer targets the
   hostname — but if anything does, this is the layer to restore. See
   [the blocklist section](#cpanels-ip-blocklist-and-how-the-deploy-carries-it-across).

   **A rollback resurrects them.** `public_html_prev` still holds the old file,
   deny lines included, so swapping it back reinstates whatever was blocked at
   the time.

### Verify, after each of steps 5 and 7

- **The client address still resolves to the visitor.** This is the one that
  silently refuses supporters:

  ```
  curl -s https://api.voteforjulia.com/health | jq -r .client
  curl -s https://api.ipify.org      # must still match
  ```

  A Cloudflare address here means `TRUSTED_CLIENT_IP_HEADER` is not in effect.
  Fix it before anything else.

- **Mail still sends _and still authenticates_.** Submit the form on the test
  site and confirm both the notification and the confirmation arrive. Then open
  the received message's headers and check `Authentication-Results` shows
  `spf=pass` and `dkim=pass`. Arrival alone is not enough: DMARC is `p=reject`,
  so a misaligned message is refused by other receivers even when it reaches an
  inbox you control. Sending to a Gmail address and using "Show original" is the
  quickest way to read that.

  Verified on 2026-08-14 with the test zone proxied:

  ```
  spf=pass   (designates 23.83.219.16 as permitted sender)
  dkim=pass  header.i=@voteforjulia.com header.s=default
  dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=voteforjulia.com
  ```

  **Outbound mail leaves through MailChannels, not the origin.** The chain is
  app → Exim on the host → `relay.mailchannels.net` → recipient, so the
  delivering address is MailChannels' and SPF passes on the `include:`, not on
  `a` or `mx`. Cloudflare is nowhere in that path — which is why proxying does
  not endanger mail, and why the only real mail risk in the migration is a
  record being lost when the zone moves.

- **No CSP violations.** Load the site **in a browser** with devtools open, and
  read the console. Several Cloudflare features inject script that the CSP
  blocks — see [Leave these off](#leave-these-off) — and a violation appears
  nowhere but the console.

  **A clean result from one place is not a clean rollout.** Cloudflare setting
  changes propagate per PoP, so the same URL can inject the beacon from one
  location and not another for a while after the switch is flipped — observed
  2026-08-12, clean from one network while `ORD` still injected. Re-check from
  more than one place, and after a delay, before calling it fixed.

  This is _not_ caching, and purging will not help: `cf-cache-status: DYNAMIC`
  on every one of those responses means Cloudflare built each one fresh from the
  origin. What is stale is the injection config at the edge, not the HTML.

  **`curl` will not find these.** Cloudflare injects its beacon only for
  browser-shaped requests, so a plain `curl` of the same URL comes back clean
  and proves nothing. To check from the shell, ask like a browser:

  ```
  curl -sL https://test.voteforjulia.com/ \
    -H 'Accept: text/html' -H 'User-Agent: Mozilla/5.0 (Macintosh) Chrome/131' \
    | grep -o 'cloudflareinsights[^"]*'
  ```

- **The e2e suite passes.** Cypress runs against `test.voteforjulia.com` from
  GitHub's Azure ranges. If a Cloudflare bot setting challenges those, the suite
  dies exactly the way it did under
  [Imunify360](#imunify360-waf-disabled) — and a challenge returns `200` with a
  splash body, so nothing goes red on its own.

### Rolling back

**Toggle the orange cloud off.** Once the nameservers are Cloudflare's, that is
a DNS change inside Cloudflare and takes effect in seconds — it is the fast
rollback for anything the proxy causes, and the one to reach for first.

Reverting the nameservers at the registrar is the slow rollback, for problems
with Cloudflare's DNS itself rather than its proxy. Budget for propagation.

`TRUSTED_CLIENT_IP_HEADER` should be cleared if you roll all the way back,
because with nothing in front of the app it is a header any caller can forge.

### The firewall rules, and how they were derived

Two custom rules block the form spammer at the edge, added 2026-08-15. **These
live only in Cloudflare's dashboard — nothing in this repo enforces them, and
nothing warns you if they are edited or deleted.** Same silent-drift problem as
[monitoring/](../monitoring/), and worth reading back before assuming they are
still there.

```
(ip.src in {80.94.95.0/24 141.98.11.0/24 158.173.74.0/24})
or (http.request.version eq "HTTP/1.0" and http.user_agent contains "Chrome/")
or (ip.src.asnum eq 204428)
```

**Do not escape the quotes inside `contains`.** Written as
`contains "\"Chrome/\""` the rule looks for a literal `"Chrome/"` _including the
quote characters_, which no User-Agent contains — the clause then matches
nothing and the rule silently degrades to its IP terms. That happened on the
first version of this rule and was invisible in Security Events, because every
block up to that point came from an address the IP terms already covered.

`ip.src.asnum eq 204428` also makes the `80.94.95.0/24` term redundant, since
that range belongs to the same provider. Left in deliberately: it keeps working
if the ASN lookup ever changes underneath.

The protocol term is the durable one. **Chrome has never spoken HTTP/1.0**, so a
request claiming `Chrome/131` over HTTP/1.0 is self-contradicting no matter how
the User-Agent is rotated — it is the only term here that survives the operator
changing hosting provider. Validated against 97,967 real requests to this origin
before it was enabled:

| Protocol | Requests |
| -------- | -------- |
| HTTP/2   | 64,373   |
| HTTP/3   | 23,949   |
| HTTP/1.1 | 9,628    |
| HTTP/1.0 | **17**   |

All 17 were crawlers — `archive.org_bot`, `NetcraftSurveyAgent`, and one Firefox
UA from a hosting range. **Matches for HTTP/1.0 _and_ a Chrome UA: zero.** The
Chrome conjunct is load-bearing: a bare HTTP/1.0 rule would block the Internet
Archive.

Rule 2 covers the provider (SS-Net, Romania) the operator rents from, so a fresh
address there is refused before it is ever seen. Both observed addresses,
`80.94.95.173` and `80.94.95.202`, sit in `80.94.95.0/24` — that narrower range
is the option if blocking a whole ASN ever feels too broad.

**Scope them to the zone, not the apex.** The spammer posts a fixed field list
and does not need the homepage, so a rule covering only `voteforjulia.com` would
leave `api.voteforjulia.com` open.

### Closing the direct-to-origin path

Why a shared secret rather than an IP allowlist is
[ADR-0020](adr/0020-authenticate-the-origin-path.md) — the short version is that
[access control sees the visitor's address](#access-control-sees-the-visitors-address-not-cloudflares),
so the allowlist refuses the proxy too.

**There are two tokens, one per environment, and neither is in the checkout.**
Production and test must not share one: the test pipeline deploys PR-head code
into `api_test` and a PR-built `.htaccess` into the test docroot, so anything in
scope there is readable by an unmerged branch. A shared value would hand
production's edge credential to any branch someone can push.

Each token has to agree in three places. **The name is the same everywhere and
only the value differs**, so nothing — not the workflows, not
[api/app.py](../api/app.py) — has to know which environment it is running in:

|                           | Production         | Test               |
| ------------------------- | ------------------ | ------------------ |
| Cloudflare Transform Rule | apex, `www`, `api` | `test`, `test-api` |
| GitHub Actions secret     | `production` env   | `test` env         |
| cPanel app env            | `api-sub`          | `api_test`         |

**`EDGE_SHARED_TOKEN` is an environment secret, not a repository one**, set once
under Settings → Environments → `production` and once under `test`. That is not
just tidiness. A repository secret is readable by any workflow that names it,
including [ci.yml](../.github/workflows/ci.yml), which runs on `pull_request`
from the pull request's own copy of the file — so a branch could add a step
referencing it and read production's token out of CI. An environment secret is
unavailable to a job that does not declare that environment, and `production`'s
deployment branch policy admits only `main`, which a `pull_request` job's ref
(`refs/pull/N/merge`) cannot satisfy. The jobs that need it already declare the
right environment; nothing else in the repository can reach production's value.

`SSH_HOST_FINGERPRINT` stays a repository secret: it is the same host either
way, and a host key fingerprint is not a credential.

The order is what keeps this from being an outage. Every step fails open, so
stopping halfway leaves the site working and the gap merely still open.

**Step 0 is a merge, and it is not optional.** The `.htaccess` gate ships as a
placeholder that the deploy substitutes, and
[the deploy runs `main`'s workflow](#deploy-workflow-changes-cannot-be-tested-from-a-pr) —
so the substitution step has to be on `main` before the branch carrying the gate
is deployed by it. Skipped once already: the combined branch put the literal
`@@EDGE_TOKEN@@` on the test docroot, where it matched no real header and 403'd
every path. Do not set the repository secret until the gate block is on `main`
either; the substitution step aborts a deploy whose build has no placeholder in
it, rather than reporting a gate it did not install.

1. **Generate the two values.** Nobody issues these — they are yours to invent,
   and inventing them badly is the failure mode. Run this once per environment,
   on your own machine, and keep the two results apart:

   ```
   openssl rand -hex 32
   ```

   **Alphanumeric, and at least 32 characters** — the deploy refuses anything
   else and aborts before the swap. The character set is a mechanical
   constraint: the value is interpolated into a `sed` replacement and then a
   `RewriteCond` regex, where a metacharacter would corrupt the file or silently
   change what the rule matches. The length is the security one. A refused
   caller is by definition one the edge's rate limiting never saw, so the 403 is
   an unmetered oracle to guess against — and guessing the token is the whole
   attack, since carrying it is the only thing the origin checks. A memorable
   value is the failure here, not a short one chosen on purpose.

2. **Create both Transform Rules.** In the dashboard: **Rules** → **Overview** →
   **Create rule** → **Request Header Transform Rule**, once per environment.
   Skip the templates, name the rule, choose the custom filter expression rather
   than "all incoming requests", and paste the matching expression below. Then
   under **Modify request header** pick **Set static**, with header name
   `X-Origin-Token` and that environment's token as the value, and **Deploy**.

   ```
   # production rule
   http.host in {"voteforjulia.com" "www.voteforjulia.com" "api.voteforjulia.com"}

   # test rule
   http.host in {"test.voteforjulia.com" "test-api.voteforjulia.com"}
   ```

   Space-separated inside the braces, no commas. The two sets are disjoint, so
   neither rule can overwrite the other's header — worth knowing because request
   header rules run in order and a later one silently wins where they overlap.

   **Every hostname in an environment must be listed** — same trap as
   [the firewall rules](#the-firewall-rules-and-how-they-were-derived): a
   production rule matching only `voteforjulia.com` leaves `api.voteforjulia.com`
   unstamped, and the API is what the spam bot posts to. Splitting one rule into
   two doubles the chances of getting this wrong, so check all five hostnames
   rather than the one you were thinking about:

   ```
   for h in voteforjulia.com www.voteforjulia.com api.voteforjulia.com \
            test.voteforjulia.com test-api.voteforjulia.com; do
     printf '%-28s ' "$h"
     curl -so /dev/null -w '%{http_code}\n' "https://$h/"
   done
   ```

   `mail.voteforjulia.com` is deliberately absent, and cannot be added even by
   mistake: **Transform Rules only apply to proxied records**, and `mail` is
   grey-clouded precisely because Cloudflare does not carry SMTP. It therefore
   never gets the header, and being refused is the entire point of this control.
   Confirmed 2026-08-18 — every other hostname answers with `server: cloudflare`
   and a `cf-ray`; `mail` answers `server: LiteSpeed` with neither.

3. **Confirm the header actually arrives**, before anything enforces. Set
   `EDGE_SHARED_TOKEN` on `api_test` to the **test** token, leave
   `EDGE_TOKEN_ENFORCED` unset, restart, then submit through the test site and
   read the app log. A warning naming `X-Origin-Token` means the rule is not
   reaching the API; silence means it is.
4. **Pin the SSH host key first**, as `SSH_HOST_FINGERPRINT`. The token is
   substituted on the runner, so the `.htaccess` upload is the one transfer in
   either workflow that carries a secret — and `appleboy`'s actions skip host
   verification entirely when `fingerprint` is empty. `scp-action` documents
   that default as "skip verification"; `easyssh-proxy` uses
   `ssh.InsecureIgnoreHostKey()`. Unpinned, anything that can answer for the
   host receives the armed file.

   **Both commands below run on your own machine**, not on the host, and the
   point is that they are two different questions. The first runs `ssh-keygen`
   _on_ the server over a session you have already accepted, so it is the
   server's own statement of its key. The second asks a fresh client what the
   host presents. A scan on its own is trust-on-first-use and would confirm an
   impostor just as readily; the two agreeing is what makes it evidence. Host
   and port come from the same [`vfj` alias](#reaching-the-host), so there is
   nothing to paste:

   ```
   ssh vfj 'ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub'

   eval "$(ssh -G vfj | awk '/^hostname /{print "H="$2} /^port /{print "P="$2}')"
   ssh-keyscan -p "$P" -t ed25519 "$H" | ssh-keygen -lf -
   ```

   Each prints four fields, and **only the second one is the fingerprint**:

   ```
   256 SHA256:F3QIAH7qTYPeWARYIWuO0GFI94UB5u8LgDGOQ8QzHYI root@host           (ED25519)
   256 SHA256:F3QIAH7qTYPeWARYIWuO0GFI94UB5u8LgDGOQ8QzHYI [203.0.113.10]:2222 (ED25519)
   ^bits                    ^ store exactly this          ^ differs, ignore   ^ key type
   ```

   Store `SHA256:…` alone — keep the prefix, drop the bit count, the trailing
   comment and the `(ED25519)`. There is no `=` padding to trim: `ssh-keygen`
   prints the unpadded form, which is exactly what `easyssh-proxy` compares
   against (`"SHA256:" + base64.RawStdEncoding`).

   **The third field is meant to differ between the two commands** — one is the
   key's comment on the server, the other the address it was scanned at. Only
   the fingerprint has to match, so `… | awk '{print $2}'` on both is the
   comparison to trust.

   If the first command cannot read the file, the host has made `/etc/ssh`
   unreadable and the scan is all there is — in that case run it from two
   different networks and compare, rather than accepting a single result.

   If the deploy later fails with a fingerprint mismatch, the server presented
   a different key type — take that type's
   fingerprint from the first command rather than pasting whatever the error
   reports. **Each deploy refuses to run once its own token secret is set and
   this is not**, so the ordering is enforced rather than remembered.

5. **Add `EDGE_SHARED_TOKEN` to the `test` environment first**, since test is
   where a mistake is survivable, then to `production` — Settings →
   Environments, not the repository secrets page — and deploy. Until an
   environment has the secret, that environment's deploy strips the gate out of
   `.htaccess` entirely rather than leaving the placeholder — a literal `@@EDGE_TOKEN@@` would demand a header
   nobody can send and refuse every visitor.
6. **Verify the frontend gate on test**, which is where a mistake is survivable:

   ```
   curl -so /dev/null -w '%{http_code}\n' https://test.voteforjulia.com/
   curl -so /dev/null -w '%{http_code}\n' \
     --resolve test.voteforjulia.com:443:208.115.234.114 https://test.voteforjulia.com/
   ```

   Want `200` then `403`. Use `--resolve`, never a `Host:` header against the
   IP — the mismatched SNI serves a different vhost and reports a misleading
   result.

7. **Check the second front door is shut, and the mail paths are not.**
   `mail.voteforjulia.com` serves the whole site from `public_html` and is never
   proxied, so it is the bypass — not, as an earlier version of this page had it,
   a hostname to keep working:

   ```
   curl -so /dev/null -w 'site   %{http_code}\n' https://mail.voteforjulia.com/
   curl -so /dev/null -w 'auto   %{http_code}\n' https://mail.voteforjulia.com/autodiscover/autodiscover.xml
   curl -so /dev/null -w 'acme   %{http_code}\n' https://voteforjulia.com/.well-known/
   ```

   Want `403`, then `400`, then not-`403`. A `200` on the first means the gate is
   scoped by `Host` and the bypass is open. A `403` on the second means the
   `[NC]` trap above has been reintroduced and mail clients cannot configure
   themselves.

   **`400` is the healthy answer for autodiscover, not `200`.** Measured
   2026-08-16, before anything enforced: cPanel answers
   `/autodiscover/autodiscover.xml` above the docroot — LiteSpeed,
   `text/plain`, identical proxied and direct — and `400` is what its handler
   returns to a `GET`. The docroot never sees that path, so the `.htaccess`
   exemption is insurance against that interception changing rather than the
   thing keeping Outlook working. What the docroot _does_ see is the
   capitalised `/AutoDiscover/AutoDiscover.xml`, which is `404` today and
   becomes `403` under the gate — a path that already did not work either way,
   which is why the exemption is spelled `[Aa]utodiscover` and does not need
   widening to `[Aa]uto[Dd]iscover`.

8. **Arm the API**: set `EDGE_TOKEN_ENFORCED=true` on `api_test`, restart,
   re-run the Cypress suite, then repeat 5–8 for production and `api`.

**Rolling back** is clearing `EDGE_TOKEN_ENFORCED` and restarting for the API,
or deleting the repository secret and redeploying for the frontend. Deleting the
Transform Rule alone rolls back nothing — it takes the header away while both
ends still demand it, which is the total outage. **Turn enforcement off before
touching the rule.**

#### Rotating the token

**There is no order that rotates in place without an outage.** The frontend
compares against exactly one value, baked into `.htaccess` at deploy time, so
between changing the Transform Rule and landing a deploy that agrees with it,
every proxied request to the site is refused — and a deploy is a full CI run,
not a dashboard edit. Changing the API last does not help: the API is the side
that fails open, and the frontend is the side that goes down.

So rotation **takes the gate down first and puts it back after**, accepting a
few minutes with the origin reachable rather than a few minutes with the site
refusing its visitors. The gap was open for months before ADR-0020; the site
being down is the worse of the two:

Each environment rotates on its own — that is the point of them being separate
— so this is done once per environment, against that environment's rule, secret
and app:

1. Clear `EDGE_TOKEN_ENFORCED` on that environment's cPanel app and restart.
2. Delete `EDGE_SHARED_TOKEN` from that environment and re-run the deploy. The
   gate block is stripped from `.htaccess`, and the frontend serves everyone.
3. Change that environment's Transform Rule to the new value.
4. Set the new secret, deploy, set the new `EDGE_SHARED_TOKEN` value on that
   app, restart, then re-arm `EDGE_TOKEN_ENFORCED` — steps 5–8 above, in order.

**Rotate the test token on its own schedule, and treat it as burnt whenever a
branch has had something questionable on it.** It is exposed to every PR by
design, which is precisely why it is not production's.

Accepting both an old and a new token for an overlap would remove the window
entirely, and is
[recorded as the alternative it is](adr/0020-authenticate-the-origin-path.md#alternatives-considered):
it needs a second placeholder in `.htaccess` and a second secret, to make an
operation that has never yet been performed slightly tidier.

Consequences worth knowing:

- **A fourth drift surface**, alongside [monitoring/](../monitoring/), the
  firewall rules and the branch protection. Nothing syncs the Transform Rules and
  nothing warns if it is edited away; the symptom is the whole site returning 403.
- **A rollback to `public_html_prev` restores whatever token was current when
  that snapshot was deployed**, which after a rotation is the wrong one — the
  [one-command rollback below](#frontend-deploys) is then itself a site-wide 403. The third thing on this page a rollback quietly resurrects, after the two
  blocklist caveats. Redeploy rather than roll back if the token has changed
  since that build.
- **Debugging with `curl --resolve` now needs the header**, or the origin
  answers 403 and looks like a different fault.

### Leave these off

- **Rocket Loader** and **Email Obfuscation** — both inject inline script; see
  the CSP check above.
- **Web Analytics / Browser Insights** — injects
  `static.cloudflareinsights.com/beacon.min.js`, which the CSP blocks. Observed
  on the test zone 2026-08-12. It is also redundant here (New Relic Browser
  already reports Core Web Vitals and client errors, per
  [ADR-0013](adr/0013-server-side-apm.md)) and, worse, **invisible to the CI
  performance budget** — that budget measures `dist/`, and an edge-injected
  script never appears there. See [performance.md](performance.md).
- **Bot Fight Mode**, at least until the e2e suite and the synthetic monitors
  have been observed passing with it on. It challenges by IP reputation, and
  both run from cloud ranges.

## Deploy workflow changes cannot be tested from a PR

Both deploy workflows trigger on `workflow_run`, and GitHub always executes the
**default branch's** copy of a `workflow_run`-triggered workflow. A change to
[deploy-test.yml](../.github/workflows/deploy-test.yml) or
[deploy-production.yml](../.github/workflows/deploy-production.yml) therefore has
no effect until it is merged to `main` — the PR's test deploy keeps running the
old steps.

The failure mode is that it looks like it worked. The deploy still succeeds, still
uploads, still restarts, so the green check says nothing about your edit. Confirm
which steps actually ran rather than inferring it from side effects on the host:

```
gh run view <run-id> --json jobs \
  --jq '.jobs[] | select(.name|test("Deploy")) | {name, steps: [.steps[].name]}'
```

If your new step name is absent, it did not run. The mitigation, where it is
available, is to keep the logic in a script the workflow merely calls: a
one-line step is hard to get wrong, and everything it invokes can be tested from
the PR like any other code. [scripts/arm-edge-gate.sh](../scripts/arm-edge-gate.sh)
is the worked example — the edge gate's substitution and its guards live there,
covered by [scripts/test_arm_edge_gate.py](../scripts/test_arm_edge_gate.py),
after starting life as ninety lines of shell embedded in both workflows where
nothing could reach them. Consequences worth planning for:

- A merge is the **first** execution of any deploy-workflow change, and for
  `deploy-production.yml` that first execution is against production.
- Verify such changes by running the underlying commands over SSH by hand first,
  then watch the first post-merge run closely.

## Frontend deploys

Both environments serve prerendered static files; `.htaccess` is uploaded as a
**separate scp step** in each workflow because the `dist/**` glob does not match
dot-prefixed files. Both also stage into a scratch directory and swap it in with
two renames, rather than uploading over the live root — see the swap below.

### cPanel's IP blocklist, and how the deploy carries it across

**cPanel's IP Blocker writes `deny from` into the `.htaccess` of _every_ document
root on the account — `public_html`, `api-sub`, `api_test`, the test docroots —
but renders its UI list from `public_html/.htaccess` alone.** That one file is
also the one the frontend deploy replaces wholesale, verbatim from
[public/.htaccess](../public/.htaccess).

Left alone, that combination fails in a way that does not look broken. A deploy
cleared the block on `voteforjulia.com`, emptied the IP Blocker screen, and left
the identical block on `api.voteforjulia.com` enforcing invisibly — an address
refused by the API with nothing in cPanel left to un-block it.

Observed on 2026-08-10. The bot's cycle the next day made the split obvious:

```
13:18:54  GET  voteforjulia.com/      200   ← block gone, page served
13:18:55  POST api.voteforjulia.com/send-email  403   ← block intact
```

**Both deploy workflows now rebuild the block into the staged `.htaccess` before
the swap**, in a `Carry cPanel IP Blocker rules into the staged .htaccess` step.
It reads the `deny from` lines out of the live docroot _and_ the matching API
docroot, normalises and de-duplicates them, and appends the union plus cPanel's
own `<Files 403.shtml>` stanza. Production pairs `public_html` with `api-sub`,
test pairs `public_html_test` with `api_test`; neither reads the other's, so a
block never crosses environments.

The union — rather than merely preserving what `public_html` had — is the part
that repairs an entry already orphaned on the API side: it reappears in the UI,
where removing it clears every docroot at once. It cannot widen enforcement,
because a unioned address is by definition already being refused by the API.

Consequences and the things still worth knowing:

- **cPanel remains the source of truth.** Blocks are added and removed from
  cPanel → IP Blocker as before; the deploy only stops destroying them. Nothing
  about the blocklist is committed to this repo, which matters because **the repo
  is public** — a `deny` in `public/.htaccess` would publish the addresses and
  keep them in history forever. The workflow logs are public too, so the step
  prints a count and never the addresses.
- **The step aborts the deploy if the staged `.htaccess` is missing or empty**,
  instead of appending deny rules to a file with no CSP in it — the silent
  total loss [ADR-0010](adr/0010-edge-policy-in-htaccess.md) warns about.
- **An empty UI still does not prove nothing is blocked.** The screen reflects
  only the main docroot. Search them all before concluding a block is gone:

  ```
  find ~ -maxdepth 3 -name .htaccess -exec grep -l "deny from" {} +
  ```

- **A `403` with a ~1.2KB body is an Apache-level block**, i.e. `.htaccess`. A
  firewall block drops the connection instead, so the response shape tells you
  which layer you are looking at.
- **A rollback rolls the blocklist back too.** Swapping `public_html_prev` back
  in restores that build's copy of the list, which is as old as the build. The
  next deploy re-unions it against `api-sub` and repairs it.
- **Blocks are still permanent until someone removes them**, and a residential IP
  reassigned to a real supporter would be refused with no diagnostic. Prefer
  defences that are not keyed on IP at all
  ([ADR-0016](adr/0016-second-tier-rate-limiting-and-honeypot.md)).

### Test — [deploy-test.yml](../.github/workflows/deploy-test.yml)

Triggered by a successful CI run on a **pull request**. A `gate` job refuses to
deploy when the run is stale (the commit is no longer branch HEAD), the PR has
been closed, the branch is Dependabot's, or the fork is external. Then:

- builds with `VITE_API_BASE_URL=https://test-api.voteforjulia.com` and
  `SOURCEMAP_MODE=true` (linked maps, so devtools resolve them),
- overwrites `robots.txt` and injects a `noindex` meta tag so the test site
  cannot be indexed,
- stages into `./public_html_test_next` and swaps it into `./public_html_test`
  (rollback copy in `./public_html_test_prev`), exactly as production does,
- runs the Cypress e2e suite against the deployed site.

Test used to scp straight into the live `./public_html_test`, which had two
consequences worth remembering, since both are easy to reintroduce. The e2e suite
could hit new HTML while `.htaccess` was still the previous copy or mid-write —
a plausible cause of the intermittent "redirected more than 20 times" Cypress
failures. And because nothing ever pruned the directory, every past deploy's
hashed assets and sourcemaps piled up in it: it had reached 70M against
production's 1.7M.

### Production — [deploy-production.yml](../.github/workflows/deploy-production.yml)

Triggered by a successful CI run on `main`, pinned to the exact commit CI
verified (`workflow_run.head_sha`), not branch HEAD.

Uploads to `./public_html_next`, then swaps atomically:

```
rm -rf public_html_prev
mv public_html public_html_prev   # rollback copy
mv public_html_next public_html
```

Two renames on one filesystem, so the live root is only briefly absent instead
of serving a half-uploaded mix. **The previous build stays in
`./public_html_prev`** — that is the rollback: swap the two directories back.

Test does the same thing with `public_html_test{,_next,_prev}`.

## The Python API

Flask under **Passenger**. Production lives in `./api`, test in `./api_test`;
[api/passenger_wsgi.py](../api/passenger_wsgi.py) aliases the package name so
`from api.… import` resolves against whichever directory it was deployed into.

Deploys scp `api/**`, install dependencies, prune, and then restart the app by
touching a file:

```
touch ./api/tmp/restart.txt
```

Unlike the frontend, the API is **not** swapped in atomically — Passenger's app
root is host configuration, so the directory has to stay put and is updated in
place. scp only adds and overwrites, which used to mean a module deleted or
renamed in the repo stayed on the host forever and stayed importable. So the
deploy writes `api/deploy-manifest.txt` (every tracked file under `api/`, minus
the test suite and `requirements-dev.txt`), uploads it with everything else, and
afterwards deletes anything present on the host that the manifest does not list:

```
find . -type f ! -path './tmp/*' ! -name deploy-manifest.txt | sed 's|^\./||' | LC_ALL=C sort > /tmp/deployed
LC_ALL=C comm -23 /tmp/deployed deploy-manifest.txt | tr '\n' '\0' | xargs -0 -r rm -f --
```

That is the shape of it; the workflows are the source of truth, and add the
guard below plus cleanup of the temporary file. Note the `tr`/`xargs -0` pair —
`comm` emits newline-separated paths, and feeding those to a bare `xargs` would
split any path containing whitespace into two arguments and delete neither.

Consequences worth knowing:

- **`tmp/` is excluded** — it is Passenger's, and `restart.txt` lives there. The
  virtualenvs are never at risk; they sit in `~/virtualenv/`, outside the app
  root.
- **The test files are uploaded and then deleted.** One mechanism decides what
  production contains, which is simpler than teaching scp-action to filter.
- **The prune refuses to run** against a manifest that is missing or under ten
  lines. Without that guard a truncated upload reads as "nothing here belongs"
  and would delete the whole application.
- **Both lists are sorted with `LC_ALL=C`.** They are produced on different
  machines and `comm` compares bytes, so a collation mismatch between the runner
  and the host would report live files as stale.

### `remote_addr` is the real client, and this is how to re-check

Nothing sits in front of the Python apps, so Flask sees the caller's own
address. **Verified on the test environment 2026-08-13**: `/health` echoed
`156.47.97.177` to a client whose egress address was `156.47.97.177`.

That had been assumed since [ADR-0009](adr/0009-in-process-rate-limiting.md) and
never checked, and it is load-bearing for every per-IP control — if it ever
resolved to a fixed private address, all of them would be one shared bucket and
a single caller could exhaust everybody's allowance while looking, from the
logs, like ordinary traffic.

```
curl -s https://api.voteforjulia.com/health | jq -r .client   # should be your address
curl -s https://api.ipify.org                                 # ...and this should match
```

Re-check it after anything that could interpose: a CDN, a proxy, a host
migration. If they stop matching, the fix is `TRUSTED_CLIENT_IP_HEADER` — set it
to the header the new thing overwrites, never to `X-Forwarded-For` on trust
([ADR-0014](adr/0014-do-not-trust-forwarding-headers.md)).

**This section stops being true the moment Cloudflare goes in front**
([ADR-0019](adr/0019-cloudflare-in-front.md)). `remote_addr` becomes a
Cloudflare address and `CF-Connecting-IP` carries the caller, which is why the
migration sets `TRUSTED_CLIENT_IP_HEADER` before proxying anything. The two
commands above stay the check — they just stop proving the same thing about
`remote_addr`, and start proving the variable is in effect. See
[the runbook](#migrating-dns-to-cloudflare).

New Relic cannot answer this for you: the agent records a fixed allowlist of
request headers, none of which carries a client address.

### Environment variables

**This is the only deployment state with no representation in the checkout.**
Nothing in the repo sets these — they are entered per app in cPanel's Python
selector, they are not in the deploy workflows, and a rebuilt app starts with
none of them. The table below is a reference, not a source of truth: read the
live values back with the command under
[Reading an app's configured environment](#reading-an-apps-configured-environment),
and mind the [`$` rule](#app-env-vars-must-not-contain-) when setting any of them.

**When a change takes effect** depends on where the variable is read, and the
split is not arbitrary. Anything in [api/config.py](../api/config.py) is read
**per request**, so it applies on the next submission with no restart — that is
what makes rotating `EMAIL_PASSWORD` a cPanel edit rather than a deploy.
Anything read at import in [api/app.py](../api/app.py) needs
`touch api/tmp/restart.txt`, because a bad value there would otherwise fail
module import and take every form down rather than degrade
(`_int_setting` logs and falls back for exactly this reason).

Mail — per request, no restart:

| Variable                       | Default                 | Notes                                                          |
| ------------------------------ | ----------------------- | -------------------------------------------------------------- |
| `EMAIL_ADDRESS`                | _none_                  | SMTP username and the `From` address. Unset ⇒ every form 500s. |
| `EMAIL_PASSWORD`               | _none_                  | Unset ⇒ every form 500s. See the `$` rule.                     |
| `SMTP_SERVER`                  | `mail.voteforjulia.com` |                                                                |
| `SMTP_PORT`                    | `465`                   |                                                                |
| `SMTP_SECURITY`                | `auto`                  | `auto` \| `ssl` \| `starttls`; `auto` means STARTTLS on 587.   |
| `SMTP_TIMEOUT_SECONDS`         | `10`                    | Raises `ValueError` (JSON 500) if unparseable or ≤ 0.          |
| `RECIPIENT_EMAIL`              | `info@voteforjulia.com` | Comma- or semicolon-separated.                                 |
| `RECIPIENT_EMAIL_SIGNS`        | falls back to the above | Yard-sign notifications only.                                  |
| `PLAIN_TEXT_CONFIRMATION_ONLY` | `false`                 | Drops the HTML part of confirmation emails.                    |

Google Sheets — per request, no restart:

| Variable                           | Default      | Notes                                                              |
| ---------------------------------- | ------------ | ------------------------------------------------------------------ |
| `GOOGLE_SHEETS_SPREADSHEET_ID`     | _none_       | **Unset ⇒ appends are silently skipped**, and the form still 200s. |
| `GOOGLE_SHEETS_WORKSHEET`          | `Sheet1`     | Title, or a numeric gid.                                           |
| `GOOGLE_SHEETS_YARDSIGN_WORKSHEET` | `Yard Signs` |                                                                    |
| `GOOGLE_SERVICE_ACCOUNT_FILE`      | _none_       | Takes precedence over the JSON form below.                         |
| `GOOGLE_SERVICE_ACCOUNT_JSON`      | _none_       | The whole key as one value; watch the `$` rule.                    |
| `SHEETS_TIMEOUT_SECONDS`           | `15`         | Larger than SMTP's: it runs after both emails are away.            |

Abuse controls — read at import, **restart required**:

| Variable                              | Default                                     | Notes                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ORIGIN_ENFORCED`                     | `true`                                      | `false` logs cross-site posts without refusing them. [ADR-0017](adr/0017-origin-trust-boundary-and-health-probe-cache.md)                                                                                                                                                                                                                                                                                           |
| `HONEYPOT_ENFORCED`                   | `true`                                      | `false` logs a filled honeypot without refusing it. [ADR-0016](adr/0016-second-tier-rate-limiting-and-honeypot.md)                                                                                                                                                                                                                                                                                                  |
| `CORS_ALLOWED_ORIGINS`                | apex, www, test, test-api, `localhost:5173` | Comma-separated. Since ADR-0017 this also decides who may _submit_, not only who may read a response.                                                                                                                                                                                                                                                                                                               |
| `RATE_LIMIT_MAX_REQUESTS`             | `5`                                         | Burst tier, per client per endpoint.                                                                                                                                                                                                                                                                                                                                                                                |
| `RATE_LIMIT_WINDOW_SECONDS`           | `60`                                        |                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `LONG_RATE_LIMIT_MAX_REQUESTS`        | `10`                                        | Sustained tier, counted in SQLite.                                                                                                                                                                                                                                                                                                                                                                                  |
| `LONG_RATE_LIMIT_WINDOW_SECONDS`      | `3600`                                      |                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS` | `30`                                        | `/health/deep` only. Raise before shortening the monitor's period.                                                                                                                                                                                                                                                                                                                                                  |
| `RATE_LIMIT_MAX_BUCKETS`              | `10000`                                     | Memory backstop; crossing it resets allowances, failing open.                                                                                                                                                                                                                                                                                                                                                       |
| `TRUSTED_CLIENT_IP_HEADER`            | _unset_                                     | **Leave unset unless something really does front the app.** Setting it lets any caller mint a fresh bucket per request. [ADR-0014](adr/0014-do-not-trust-forwarding-headers.md)                                                                                                                                                                                                                                     |
| `MAX_CONCURRENT_SUBMISSIONS`          | `12`                                        | Submissions served at once, across all workers; the overflow gets a 503. Sized against the LVE memory cap, not the process cap. [ADR-0018](adr/0018-cap-concurrent-submissions.md)                                                                                                                                                                                                                                  |
| `MAX_CONCURRENT_HEALTH_PROBES`        | `2`                                         | `/health/deep`'s own slot budget, counted separately so a probe flood cannot close the forms.                                                                                                                                                                                                                                                                                                                       |
| `INFLIGHT_TTL_SECONDS`                | unset (derives; `270` on default timeouts)  | How long a slot survives unreleased, for a worker killed mid-request. Derived **per request** from the configured timeouts, so raising `SMTP_TIMEOUT_SECONDS` raises this automatically — it bounds each socket operation, not the session, and a session is a dozen of them. Set a value only to pin it; leave it unset to derive. `/health/deep` gets a shorter bound of its own, since a probe is half the work. |
| `MAX_REQUEST_BYTES`                   | `65536`                                     | Bodies above this are refused with 413 before parsing.                                                                                                                                                                                                                                                                                                                                                              |

Ops — read at import, **restart required**:

| Variable                    | Default | Notes                                                                                                                |
| --------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------- |
| `HEALTH_DEEP_CACHE_SECONDS` | `60`    | Keep well under the synthetic monitor's period. [ADR-0017](adr/0017-origin-trust-boundary-and-health-probe-cache.md) |
| `NEW_RELIC_LICENSE_KEY`     | _unset_ | Unset ⇒ the agent never starts and the app runs uninstrumented.                                                      |
| `NEW_RELIC_APP_NAME`        | _unset_ | Read by the agent, not by our code. See [New Relic agent environment](#new-relic-agent-environment).                 |
| `PORT`                      | `5000`  | `python -m api.app` only; Passenger does not use it.                                                                 |

Two defaults are worth reading twice, because both fail quietly rather than
loudly: an unset `GOOGLE_SHEETS_SPREADSHEET_ID` makes every submission return
200 with no row written, and an unset `NEW_RELIC_LICENSE_KEY` means a healthy
site reporting no server-side telemetry at all.

### Dependencies: installed by the deploy, pinned in the repo

Each app has its own cPanel-managed virtualenv, created by the CloudLinux Python
selector rather than by us:

```
/home/juliafor/virtualenv/api/3.11/       # production
/home/juliafor/virtualenv/api_test/3.11/  # test
```

Both deploy workflows install dependencies into the app's virtualenv between the
scp and the Passenger restart, via the selector rather than a direct `pip`:

```
/usr/sbin/cloudlinux-selector install-modules --json --interpreter python \
  --app-root api --requirements-file requirements.txt
```

Invoke it by absolute path, as every example here and both workflows do. A bare
`cloudlinux-selector` does resolve today — `/usr/sbin` is currently on the `PATH`
even for a non-interactive SSH shell — but that `PATH` is cPanel's to change, and
the absolute path costs nothing and makes these snippets safe to paste straight
into a deploy script.

Three things about that command are load-bearing:

- **It exits 0 even when pip fails.** The only reliable signal is the JSON
  `result` field, so both workflows match on `"result": "success"` and `exit 1`
  otherwise. A bare `pip install ...` in an ssh script would silently "succeed"
  on a broken install.
- **It resolves the virtualenv from the app's own config**, so it keeps working
  across interpreter changes. Do not hardcode
  `~/virtualenv/api/3.11/bin/pip` — and note a `~/virtualenv/api/*/bin/pip` glob
  is now ambiguous, because switching the Python version leaves the old
  version's directory behind (the retired `3.9/` trees are still on disk).
- **Ordering matters.** The install step runs before the restart, so a failed
  install stops the job with the old worker still serving the old code, instead
  of booting new code against dependencies that were never installed.

[api/requirements.txt](../api/requirements.txt) pins exact versions (`==`), which
is what makes CI meaningful: it installs the same versions production runs. Keep
it that way — with ranges, CI and the host resolve independently and can differ.

### New Relic agent environment

The APM agent ([ADR-0013](adr/0013-server-side-apm.md)) is configured entirely
through the Passenger environment — there is no `newrelic.ini`. Set these per
app in the cPanel Python selector:

| Variable                | `api`              | `api_test`              |
| ----------------------- | ------------------ | ----------------------- |
| `NEW_RELIC_LICENSE_KEY` | ingest licence key | same key                |
| `NEW_RELIC_APP_NAME`    | `voteforjulia-api` | `voteforjulia-api-test` |

Use the **ingest licence key** (40 hex characters ending `NRAL`), not the
`NRAK-` user key the source map upload uses — they are different credentials and
the agent silently fails to report with the wrong one. Being hex, the licence key
is safe under the `$`-in-`SetEnv` hazard above; the app name is ASCII letters and
dashes, likewise safe.

**With `NEW_RELIC_LICENSE_KEY` unset the agent does not start**, and the app
serves normally without it. That is the intended local and CI behaviour, and it
is also the fallback if the agent ever misbehaves: clear the variable and
restart, no deploy needed.

Confirm a worker is actually reporting by checking the app appears in New Relic,
or query `SELECT count(*) FROM Transaction WHERE appName = 'voteforjulia-api'`.
The `Transaction` event type does not exist for this account until the agent
reports, so its presence is itself the signal.

#### Watch worker memory

Measured on the host, the agent costs **about +12MB** per worker (baseline
interpreter ~9MB, Flask +22MB, agent +12MB). This is the cost
[ADR-0011](adr/0011-browser-side-observability.md) declined to pay, and it is
smaller than that record assumed.

**Workers are ephemeral, which defeats the obvious measurement.** Passenger on
this host spawns them per request and reaps them when idle — `ps` at a quiet
moment returns _nothing at all_, and a lone worker caught between requests looks
identical with and without the agent. Comparing one before-reading to one
after-reading proves nothing. Generate sustained traffic and measure during it:

```
ssh vfj '(for i in $(seq 1 12); do curl -s -o /dev/null https://test-api.voteforjulia.com/health/deep; sleep 1; done) &
         sleep 4
         for p in $(pgrep -f api_test/passenger_wsgi.py); do
           echo "$p pss=$(awk "/^Pss:/{print \$2}" /proc/$p/smaps_rollup)KB agent=$(grep -ci newrelic /proc/$p/maps)"
         done'
```

Two things that matter in that command:

- **Use PSS, not RSS.** Forked workers share pages, and RSS counts them in full
  for every process, so summing the RSS column badly overstates the total.
  `smaps_rollup` divides shared pages proportionally.
- **`grep -ci newrelic /proc/<pid>/maps` is the ground truth for "is the agent
  running"** — it counts the agent's mapped C extensions. Memory figures alone
  are too noisy to answer it. Note this only sees _file-backed_ mappings, so it
  says nothing about pure-Python imports.

Expect real workers around 80–115MB PSS under load and roughly zero at idle,
since none are resident.

**The account's LVE limits**, read from cPanel → Resource Usage on 2026-08-01
with the agent live in both environments:

| Limit               | Cap  | Observed |
| ------------------- | ---- | -------- |
| Physical memory     | 3GB  | ~0.5GB   |
| Number of processes | 300  | ~10      |
| Entry processes     | 200  | ~0       |
| CPU                 | 100% | <20%     |

**Faults: none**, across all seven categories cPanel tracks (CPU, EP, VMem,
Nproc, PMem, IO, IOPS). That is the number that matters. The usage graphs plot
averages and can hide a brief spike, but a zero fault count means no limit was
ever actually hit — so the headroom is real rather than merely plausible, and
it is why [ADR-0013](adr/0013-server-side-apm.md) went ahead despite
[ADR-0011](adr/0011-browser-side-observability.md)'s memory objection.

Two caveats against reading too much into it. The sample was ~4.5 hours
overnight, and most of the visible activity was the deploy and its own
verification traffic — so it says nothing about a genuine surge, and spiky,
deadline-bound traffic is precisely the pattern ADR-0013 was written against.
Re-check this page after the first real one (a yard-sign push, the week before a
vote) rather than treating the question as settled.

If memory does approach the cap, clear `NEW_RELIC_LICENSE_KEY` on the affected
app — that disables the agent without a deploy — and revisit ADR-0013.

#### Reading an app's configured environment

What each variable does is under
[Environment variables](#environment-variables); this is how to see what an app
actually has set.

`/proc/<pid>/environ` only works while a worker happens to be alive. The durable
source is the selector, but its `get` output embeds `EMAIL_PASSWORD` and the
Sheets IDs, so never print it raw. The app configs are nested at
`available_versions.<version>.users.<user>.applications`, and this prints
variable _names_ only:

```
/usr/sbin/cloudlinux-selector get --json --interpreter python > /tmp/.s && \
~/virtualenv/api_test/3.11/bin/python -c '
import json
d = json.load(open("/tmp/.s"))
for ver, vd in d.get("available_versions", {}).items():
    for app, cfg in vd.get("users", {}).get("juliafor", {}).get("applications", {}).items():
        print(app, sorted((cfg or {}).get("env_vars", {})))
'; rm -f /tmp/.s
```

#### Mind the interpreter floor

The host interpreter is the constraint that bites here. `google-auth` 2.51+
requires Python >= 3.10, so while the venvs ran 3.9 the declared requirements
were **unsatisfiable on the host** — a state that went unnoticed for as long as
nothing on the deploy path read the file. Before pinning past a dependency's
major jump, check its `Requires-Python` against the venv.

To change the interpreter (this destroys and rebuilds the venv, so the app has no
packages for the duration — do `api_test` first and verify):

```
/usr/sbin/cloudlinux-selector set --json --interpreter python --app-root api_test --new-version 3.11
```

The rebuild reinstalls from `requirements.txt` itself. Confirm which venv
Passenger is actually using with:

```
/usr/sbin/cloudlinux-selector get --json --interpreter python | tr '{},' '\n\n\n' | grep activate_path
```

Filter that output — the unfiltered `get` prints every app's Passenger
environment variables, **including `EMAIL_PASSWORD` and the Sheets IDs**. Never
pipe it somewhere that gets logged, and never run it in CI.

Keep CI's `python-version` in [ci.yml](../.github/workflows/ci.yml) equal to the
host's; testing on a version the host doesn't run is how the 3.9/3.11 gap hid.

## Caching

`.htaccess` sets long-lived immutable caching **only** for Vite's
content-hashed assets, matched by a rewrite rule that tags them with
`IS_VITE_ASSET`. HTML is `no-cache, must-revalidate` so navigation picks up new
deploys immediately. When testing a header change, hard-refresh — an already
open tab can hold onto the old response headers.
