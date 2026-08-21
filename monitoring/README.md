# monitoring

New Relic definitions, kept here because New Relic has no export-to-git story.

- `dashboard.json` — the "Vote for Julia — Site Health" dashboard. Import via
  Dashboards → Import dashboard. This is **export** format and `dashboardUpdate`
  will not accept it unmodified; if you want to push it with the API instead,
  read [Pushing dashboard.json back to New Relic](../docs/monitoring.md#pushing-dashboardjson-back-to-new-relic)
  first.
- `alerts.graphql` — synthetic monitors, both alert policies, their conditions,
  and the notification destination, channels and workflows, as NerdGraph
  mutations. Runnable from https://api.newrelic.com/graphiql or the New Relic
  CLI; the file's header covers which parts of it lie about succeeding.

Nothing syncs these with the live account. Change one, change the other.

Full context — what fires, and what to do when it does — is in
[docs/monitoring.md](../docs/monitoring.md).
