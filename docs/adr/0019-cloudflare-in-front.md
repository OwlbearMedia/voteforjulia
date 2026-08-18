# 0019. Put Cloudflare in front of the web hostnames

**Status:** Accepted
**Date:** 2026-08-12

> **Migrated 2026-08-15.** Every web hostname is proxied and `mail` is not; the
> verification results are in
> [../hosting.md](../hosting.md#migrating-dns-to-cloudflare), which also carries
> the runbook this was executed from. Two consequences below were written before
> the move and turned out to be wrong; both are marked and corrected in place
> rather than quietly deleted, because the mistake is the useful part.

Amends [0010](0010-edge-policy-in-htaccess.md), which put all edge policy in
`.htaccess`. Header, caching and URL policy stay there. What moves is the part
`.htaccess` has proved a bad home for: deciding who is allowed to reach the
origin at all.

## Context

A spam bot has been submitting the volunteer form since 2026-08-10. Four
controls were added in response —
[0016](0016-second-tier-rate-limiting-and-honeypot.md)'s hourly rate-limit tier
and honeypot, [0017](0017-origin-trust-boundary-and-health-probe-cache.md)'s
origin check, [0018](0018-cap-concurrent-submissions.md)'s concurrency cap — and
none of them is what stopped it. **cPanel IP blocks are.** That matters, because
IP blocking is the one control here that does not scale:

- The operator has used at least three addresses and rotates five User-Agent
  strings. Each new address is a manual block.
- A blocked address still reaches the server. `80.94.95.173` alone took **604
  refused requests in one day**, every one of them costing a connection, a
  response and a log line.
- The block is invisible to the application, so the log forensics needed to tell
  the bot from a supporter is a manual read of Apache logs over SSH.
- Keeping the blocklist alive at all required teaching the deploy about it
  ([#136](https://github.com/OwlbearMedia/voteforjulia/pull/136)), because
  replacing `public_html/.htaccess` was silently erasing half of it.

The honeypot — the one control designed to work regardless of address — is
**still untested against this bot**, because the IP block prevents it from
fetching the page that carries the field. So the campaign is relying on the
least scalable control while the most promising one cannot be evaluated.

Everything runs on one shared host behind a single IP, `208.115.234.114`, with
no capacity to absorb a real flood and no edge in front of it.

## Decision

**Proxy the web hostnames through Cloudflare and move who-may-connect decisions
to its edge.** `.htaccess` keeps header, caching and URL policy per
[0010](0010-edge-policy-in-htaccess.md).

Every record on the account, and what happens to it:

| Record                                  | Proxied | Why                                      |
| --------------------------------------- | ------- | ---------------------------------------- |
| `voteforjulia.com`, `www`               | **yes** | the site the bot fetches                 |
| `api.voteforjulia.com`                  | **yes** | the endpoint it posts to                 |
| `test`, `test-api`                      | **yes** | migrated first, as the rehearsal         |
| `mail`                                  | **no**  | SMTP is not proxied; mail would break    |
| `cpanel`, `webmail`, `webdisk`, `ftp`   | **no**  | non-HTTP ports Cloudflare does not carry |
| `autodiscover`, `autoconfig`            | **no**  | mail-client setup; follows `mail`        |
| MX → `mail`                             | **n/a** | must keep resolving to the origin        |
| SPF, DKIM (`default._domainkey`), DMARC | **n/a** | TXT; must survive the move byte-for-byte |

Proxying is the _smaller_ half of the risk. The larger half is that
**Cloudflare's importer cannot do a zone transfer, so it guesses**: it probes
common labels and imports what answers. It missed `test-api` on this zone, and
anything it misses stops resolving the moment the nameservers change. The
authoritative list is cPanel → Zone Editor, and it has to be diffed by hand
against what Cloudflare imported before the registrar is touched.

Three changes outside DNS:

- **`TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP`** in both cPanel apps, applied
  and restarted **before** production is proxied.
  [0014](0014-do-not-trust-forwarding-headers.md) added this variable for
  exactly this moment. Without it `request.remote_addr` is a Cloudflare address
  and every visitor collapses into one rate-limit bucket, so 0009's 5-per-60s
  burst limit starts refusing real supporters.
- **IP blocking moves to Cloudflare.** The original plan also deleted the
  `deny from` lines on the theory that they would match nothing once traffic
  arrived via Cloudflare. That theory was wrong — the host restores the real
  client address, so they do still enforce — but they were removed anyway, on
  2026-08-15, for a different and better reason: Cloudflare covers every caller
  that targets a hostname, and an origin blocklist that only grows will
  eventually refuse a real supporter whose address was reassigned. The cost is
  that direct-to-address traffic is now unfiltered; see the consequence below on
  why that path exists at all.
- **Rocket Loader and Email Obfuscation stay off.** Both inject inline script.
  The CSP in [public/.htaccess](../../public/.htaccess) allows scripts only from
  `'self'` and a named allowlist, with no `unsafe-inline`, so the browser
  refuses them and the only symptom is a console error.

## Consequences

- **A dropped mail record does not degrade delivery, it stops it.** DMARC is
  published as `p=reject` with strict alignment (`adkim=s; aspf=s`), so mail
  that fails to align is refused by the receiver rather than filed as spam. The
  campaign emails volunteers on every submission, so losing SPF, DKIM or the MX
  in the migration is an outage of the thing the site exists to do — and one
  that looks, from our side, like nothing at all.
- **Proxying does not affect outbound mail, because outbound mail never
  egresses from the origin.** Verified against a real confirmation email on
  2026-08-14, after the test zone was proxied: the host hands the message to
  **MailChannels**, which delivers it, so the receiving server sees
  `23.83.219.16` (`relay.mailchannels.net`) rather than `208.115.234.114`. SPF
  therefore passes on the `include:relay.mailchannels.net` mechanism, and the
  `a` and `mx` mechanisms in `v=spf1 a mx include:relay.mailchannels.net ~all`
  are not what carries it.

  An earlier draft of this record claimed the opposite — that proxying the root
  A record would repoint `a` at Cloudflare and leave delivery resting on `mx`.
  That was reasoned from the SPF record without checking the delivery path, and
  the headers disprove it. The practical consequence is that **the mail risk in
  this migration is entirely about DNS records surviving the move**, not about
  which records are proxied.

- **The origin stays reachable directly, so this is a filter and not a wall.**
  `mail.voteforjulia.com` cannot be proxied and resolves to the same
  `208.115.234.114` as the website, so the origin IP is readable from the MX
  record by anyone who looks. A caller that hits the IP with a `Host:` header
  bypasses Cloudflare entirely. It stops the bot in front of us, which targets
  the hostname; it does not stop anyone who reads DNS. Closing that needs the
  origin restricted to Cloudflare's ranges, which is a separate decision and is
  **not** part of this one — tracked as
  [#141](https://github.com/OwlbearMedia/voteforjulia/issues/141). Removing the
  `deny from` lines widened this path rather than leaving it as drafted: the
  hostname is now better defended than the address behind it.
- ~~**The access logs stop identifying visitors.**~~ **Wrong — the host does
  restore the real client address.** Measured after the cutover: of every client
  address in the origin's access log, **zero** were in Cloudflare's ranges, and
  the log still shows individual visitors including IPv6. So the per-IP forensics
  used throughout this incident keeps working exactly as before, and Cloudflare's
  dashboard is an addition rather than a replacement.

  This one was written from "unless the host runs `mod_remoteip`" and then
  asserted the branch that had not been checked.

- **A new dependency sits in the request path.** Previously only the host could
  take the site down. Now a Cloudflare misconfiguration or outage can too, and
  the recovery is a DNS change with propagation delay rather than a deploy.
- **The rate limiter's correctness now depends on an environment variable.**
  If `TRUSTED_CLIENT_IP_HEADER` is ever cleared while Cloudflare is in front,
  every visitor shares a bucket and the forms start refusing people. That is a
  silent, config-only failure with no test that can catch it.
- **[#136](https://github.com/OwlbearMedia/voteforjulia/pull/136)'s carry-across
  step becomes mostly vestigial.** It stays, because origin-level blocks remain
  the only defence against direct-to-IP traffic, but the blocklist it protects
  should be close to empty once Cloudflare holds the rules.
- **Bot filtering has to be introduced carefully.** Bot Fight Mode challenges by
  IP reputation, which is how Imunify360 made the Cypress suite unrunnable
  ([../hosting.md](../hosting.md#imunify360-waf-disabled)). The e2e suite hits
  `test.voteforjulia.com` from GitHub's Azure ranges and the synthetic monitors
  hit `/health/deep` from AWS; both are candidates for a challenge, and a
  challenge returns `200` with a splash body, so nothing goes red.
- **No cost.** The free tier covers IP rules, WAF custom rules and caching.
- **Caching behaviour is unchanged by default.** The free tier caches by file
  extension and passes HTML through, so `.htaccess`'s `Cache-Control` rules stay
  authoritative. A later "Cache Everything" rule would make deploys serve stale
  HTML until purged, and would need a purge step in both deploy workflows.

## Alternatives considered

- **Keep blocking at the origin.** The status quo. Works, and has already cost a
  deploy-workflow change, a documentation section, and a manual block per
  address, while leaving 604 refused requests a day hitting the server.
- **Turnstile or a CAPTCHA.** [0009](0009-in-process-rate-limiting.md) declined
  this on conversion grounds and that still holds: a volunteer sign-up is the
  conversion the site exists for. Cloudflare makes it available later without
  committing to it now.
- **Content inspection on the message body.** Probably the next lever if the
  honeypot turns out not to catch this bot, and it needs no infrastructure — but
  it addresses junk reaching the inbox, not traffic reaching the server.
- **Moving to a host with an edge.** Disproportionate for one municipal race,
  and [0001](0001-shared-hosting-over-aws.md) settled that trade already.
