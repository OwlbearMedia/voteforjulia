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
rewrites it.

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

**The host disabled Imunify360 for the whole site on 2026-08-01**, at our
request, after it made the Cypress suite unrunnable. Nothing should challenge
requests now.

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

If your new step name is absent, it did not run. Consequences worth planning for:

- A merge is the **first** execution of any deploy-workflow change, and for
  `deploy-production.yml` that first execution is against production.
- Verify such changes by running the underlying commands over SSH by hand first,
  then watch the first post-merge run closely.

## Frontend deploys

Both environments serve prerendered static files; `.htaccess` is uploaded as a
**separate scp step** in each workflow because the `dist/**` glob does not match
dot-prefixed files. Both also stage into a scratch directory and swap it in with
two renames, rather than uploading over the live root — see the swap below.

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

Deploys scp `api/**` and then restart the app by touching a file:

```
touch ./api/tmp/restart.txt
```

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
