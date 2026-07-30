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
