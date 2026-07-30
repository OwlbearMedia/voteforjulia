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

### Gotcha: deploys never install Python dependencies

Neither workflow runs `pip install`. [api/requirements.txt](../api/requirements.txt)
declares ranges (`google-auth>=2.55.2,<3`) with no lockfile, and nothing on the
deploy path reads it. Consequences:

- A Dependabot bump to `requirements.txt` merges, goes green, deploys — and
  changes nothing on the server.
- The versions actually running in production are not recorded anywhere in this
  repo.

Upgrading an API dependency means installing it on the host by hand.

## Caching

`.htaccess` sets long-lived immutable caching **only** for Vite's
content-hashed assets, matched by a rewrite rule that tags them with
`IS_VITE_ASSET`. HTML is `no-cache, must-revalidate` so navigation picks up new
deploys immediately. When testing a header change, hard-refresh — an already
open tab can hold onto the old response headers.
