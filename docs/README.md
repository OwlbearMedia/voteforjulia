# Documentation

The things the source can't tell you: why the site is built the way it is, what
the host does differently, and what to check when something breaks at 2am.

**Start at the [root README](../README.md)** if you want the site running — it
covers install, the dev server, the test suites and the deploy pipelines, and
its _Documentation_ section introduces each file below in a paragraph. This page
is the signpost for when you are already in here.

## Which file answers which question

| Question                                               | File                                           |
| ------------------------------------------------------ | ---------------------------------------------- |
| What runs where, and how does a submission flow?       | [architecture.md](architecture.md)             |
| Why was it built this way, and what else was tried?    | [adr/](adr/)                                   |
| How does this codebase do things?                      | [conventions.md](conventions.md)               |
| What does the host do that a normal server does not?   | [hosting.md](hosting.md)                       |
| Why did CI fail on size or Lighthouse?                 | [performance.md](performance.md)               |
| Something is broken — what watches it, and is it real? | [monitoring.md](monitoring.md)                 |
| Why does the CSP have those entries?                   | [donate-integration.md](donate-integration.md) |

The API also has an OpenAPI 3.1 spec at [../api/openapi.yaml](../api/openapi.yaml),
which [../api/test_openapi_spec.py](../api/test_openapi_spec.py) keeps honest
against the code.

## Which file owns a new fact

One file owns each fact and the rest link to it. A fact written down twice is a
fact that will be corrected once.

- **A decision, with a real alternative that lost** → a new record in [adr/](adr/).
  Accepted records are append-only: write the next number and mark the old one
  superseded rather than editing it. [adr/README.md](adr/README.md) has the
  template and the status values.
- **What the system is, rather than why** → [architecture.md](architecture.md).
- **A rule for writing code here** → [conventions.md](conventions.md).
- **Something true only of this host or these pipelines** → [hosting.md](hosting.md).
- **A number CI enforces** → [performance.md](performance.md), and move the
  threshold in the same commit as the change that needs it.
- **Something you would want at 3am** → [monitoring.md](monitoring.md), in the
  runbook rather than the reference half.

In code, prefer a pointer to an explanation: `See ADR-0017.` beats a paragraph
restating it. The comment is the copy least likely to be updated when the
argument changes, and a confidently wrong comment is worse than none.

## Correcting something

**When you correct a dated or factual claim, grep the tree for the date, for the
claim, and for any literal the claim is about** — a constant, a threshold, a
query fragment, an ID — and fix every copy in the same commit.

The copy that matters most is rarely the one that repeats the fact. It is the
one that _reasons from_ it: a runbook that tells you a control is weak, or a
paragraph deriving a conclusion two steps on. Ask who acts on the fact, not who
restates it. Both times this has gone wrong here, the stale copy was found by
searching for a literal rather than for prose.

Some of what these files describe is state that **nothing syncs**: the New Relic
dashboard and alerts in [../monitoring/](../monitoring/), the Cloudflare rules,
and `main`'s branch protection, which exists only in the GitHub API. Each is
flagged in the file that covers it. A UI change there needs a matching commit,
and nothing will warn you.

## Formatting

Prettier covers `docs/**/*.md`, and CI checks it, so **run `pnpm format` after
editing anything in here** or `Typecheck and frontend tests` fails on a
whitespace diff. Prose is hard-wrapped at 80 columns; tables and links are left
alone.
