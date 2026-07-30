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

## Frontend deploys

Both environments serve prerendered static files; `.htaccess` is uploaded as a
**separate scp step** in each workflow because the `dist/**` glob does not match
dot-prefixed files.

### Test — [deploy-test.yml](../.github/workflows/deploy-test.yml)

Triggered by a successful CI run on a **pull request**. A `gate` job refuses to
deploy when the run is stale (the commit is no longer branch HEAD), the PR has
been closed, the branch is Dependabot's, or the fork is external. Then:

- builds with `VITE_API_BASE_URL=https://test-api.voteforjulia.com` and
  `SOURCEMAP_MODE=true` (linked maps, so devtools resolve them),
- overwrites `robots.txt` and injects a `noindex` meta tag so the test site
  cannot be indexed,
- uploads to `./public_html_test`,
- runs the Cypress e2e suite against the deployed site.

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
