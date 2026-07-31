# Architecture decision records

One file per decision that would otherwise have to be reverse-engineered from
the code — the ones where the obvious choice was not the chosen one, or where
undoing the choice would touch several places at once. Routine choices
(Tailwind's breakpoints, which test runner) do not need a record; they live in
[../conventions.md](../conventions.md).

The map that ties them together is [../architecture.md](../architecture.md).

## Status values

- **Accepted** — in force. Everything here is currently Accepted.
- **Superseded by NNNN** — replaced. Leave the original file in place and add
  the pointer; the history is the point.
- **Deprecated** — no longer applies and nothing replaced it.

Never edit a decision out of an accepted ADR. If it changes, write the next one
and mark this one superseded.

## Adding one

Copy the next number, keep it short — a page is plenty — and remember that
_Consequences_ is the section future readers actually need: what this makes
easy, what it makes hard, and what it now rules out.

```markdown
# NNNN. Short imperative title

**Status:** Accepted
**Date:** YYYY-MM-DD

## Context

The forces at play: constraints, cost, the host, what was tried before.
Written so someone who disagrees with the outcome would still recognise the
problem.

## Decision

What we do, in the present tense.

## Consequences

What follows — including the costs accepted and the things now foreclosed.

## Alternatives considered

Each with the reason it lost.
```

Dates are when the decision was recorded, which for 0001–0012 is later than
when it was made — they were written down after the fact, from the code.
