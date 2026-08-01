# monitoring

New Relic definitions, kept here because New Relic has no export-to-git story.

- `dashboard.json` — the "Vote for Julia — Site Health" dashboard. Import via
  Dashboards → Import dashboard.
- `alerts.graphql` — synthetic monitors, alert policy, and conditions, as
  NerdGraph mutations for https://api.newrelic.com/graphiql.

Nothing syncs these with the live account. Change one, change the other.

Full context — what fires, and what to do when it does — is in
[docs/monitoring.md](../docs/monitoring.md).
