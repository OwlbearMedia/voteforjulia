# 0001. Host on shared cPanel/LiteSpeed rather than AWS

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The default architecture for a site like this — and the one the author reaches
for by habit — is containers on AWS: the built frontend in S3 behind CloudFront,
the API as a Docker image on ECS Fargate behind an ALB, with CloudWatch, IAM,
and a Terraform or CDK stack to define it all. That is the right shape for a
product that has to scale, run in more than one region, or survive an on-call
rotation.

None of those forces are present here:

- **It is a municipal campaign site with a hard end date.** Traffic is a few
  hundred visits a day, spiking around events and the election, and the site
  becomes irrelevant the day after the vote.
- **Cost is the binding constraint.** A campaign budget spends on lawn signs and
  literature, not infrastructure. The AWS shape is perhaps $30–60/month before
  anyone visits — an ALB alone costs more per month than the whole site does —
  and it is billed as several line items that each need watching. Shared hosting
  is a flat annual fee already being paid for the domain and mailboxes.
- **There is one developer**, who is also the person who would be paged.
  Infrastructure that needs maintenance is a real cost, not a rounding error.
- **The dynamic surface is three form posts.** There is no session state, no
  user accounts, no background jobs, and no data to shard.

The host that came with the domain already runs LiteSpeed and cPanel, with
CloudLinux's Python selector for WSGI apps.

## Decision

Run the whole site on the existing shared cPanel host. The frontend is static
files in a document root served directly by LiteSpeed; the API is a Flask app
under Passenger in a cPanel-managed virtualenv. No containers, no cloud
provider, no infrastructure-as-code.

Every downstream decision that looks odd out of context follows from this one:
prerendering ([0002](0002-static-site-generation.md)), scp deploys
([0006](0006-scp-deploy-with-atomic-swap.md)), in-process rate limiting
([0009](0009-in-process-rate-limiting.md)), and policy in `.htaccess`
([0010](0010-edge-policy-in-htaccess.md)).

## Consequences

- **Cost is effectively zero at the margin.** Adding pages or traffic does not
  change the bill.
- **The runtime is not ours to choose.** The Python interpreter belongs to the
  host's virtualenv ([0008](0008-pin-python-to-host.md)), the web server's
  `.htaccess` parser is LiteSpeed's rather than Apache's, and cPanel rewrites
  the generated environment-variable file — which is how a `$` in a password
  once caused real downtime (see
  [../hosting.md](../hosting.md#app-env-vars-must-not-contain-)).
- **No horizontal scaling and no failover.** One host, one process per app. If
  the host is down, the site is down; the mitigation is that the site is static
  and cacheable, and a form outage is recoverable by hand.
- **No managed observability.** There is no CloudWatch equivalent, hence
  [0011](0011-browser-side-observability.md).
- **Deploys are file copies over SSH**, with the failure modes that implies —
  addressed rather than avoided in [0006](0006-scp-deploy-with-atomic-swap.md).
- **The exit is cheap if it is ever needed.** `dist/` is a static bundle any
  object store will serve, and the Flask app is a stock WSGI app with no host
  coupling outside `passenger_wsgi.py`. Nothing here has to be unwound to move
  to AWS later; that was a condition of accepting the shared host.

## Alternatives considered

- **S3 + CloudFront for the frontend, ECS Fargate for the API.** The habitual
  choice, and technically better in every dimension that does not matter here.
  Rejected on cost and operational overhead for a site with a three-month
  lifespan and no scaling story to tell.
- **S3 + CloudFront, with the API as a Lambda behind API Gateway.** Much closer
  on cost, and a reasonable fit for two endpoints. Rejected because the shared
  host was already paid for and already runs the mail server the API sends
  through; splitting the API onto AWS would mean SMTP credentials in two places
  and a second deploy path for no saving.
- **A PaaS (Render, Fly.io, Railway).** Free tiers cold-start, and the paid
  tiers cost more than the entire hosting plan. Also a second vendor to manage.
- **Static site only, with a form-handling SaaS.** Genuinely tempting, and it
  would have removed the API entirely. Rejected because the campaign needed
  submissions in a specific Google Sheet _and_ a branded confirmation email to
  the submitter, and the per-submission pricing of the services that do both
  was worse than writing 400 lines of Flask.
