# 0004. No database — email plus a Google Sheet is the system of record

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The API receives two kinds of submission: contact and volunteer messages (one
form, embedded on the home and volunteer pages) and yard-sign requests.
Something has to store them.

The people who actually use this data are campaign volunteers, not developers.
What they need is to see who signed up, sort by neighbourhood, tick off
delivered yard signs, and hand a list to whoever is doing door-knocking that
weekend. What they do _not_ need is a login to an admin panel that only one
person can fix.

Volume over the whole campaign is expected in the hundreds of rows. The shared
host offers MySQL, so a database was available at no extra cost.

## Decision

Do not store submissions in the application. Each submission fans out to:

1. **A notification email to the campaign** — the durable copy, and the thing
   that alerts a human.
2. **A confirmation email to the submitter** — a branded receipt.
3. **A row appended to a Google Sheet**, via a service account
   ([api/services/sheets_service.py](../../api/services/sheets_service.py)).
   Contact/volunteer submissions and yard-sign requests go to separate
   worksheets.

The API keeps no state between requests except the rate-limit buckets.

## Consequences

- **The campaign gets a working back office for free** — sorting, filtering,
  sharing, phone access, and a change history, all in a tool volunteers already
  know. No admin UI was built, and none needs maintaining.
- **The API is stateless**, so a Passenger restart, a redeploy, or a rollback
  loses nothing. There are no migrations, no backups to arrange, and no
  credentials to a datastore beyond the service account key.
- **Write failures are the interesting failure mode**, since there is no local
  queue to retry from. The pipeline handles this by ordering the fan-out and
  reporting precisely: the notification email is the commit point, and a sheet
  append that fails after it returns a 502 saying "Email sent, but failed to
  save submission" while dumping the raw body to the log so the row can be
  recreated by hand.
- **Google Sheets' API is now on the critical path of a form post**, with its
  quotas and occasional latency. The service client is cached across requests
  because building it parses the key and constructs an API resource each time.
- **Supporter PII lives in a Google Sheet and in mailboxes**, which is the same
  place campaign data would have lived anyway — but it means access control is
  the sheet's sharing settings, and it is why the application log deliberately
  records field _names_ only.
- **Anything needing a query is out of reach.** No de-duplication of repeat
  submitters, no "how many volunteers this week" without opening the sheet. If
  that is ever needed, it is a new decision, not a tweak.

## Alternatives considered

- **MySQL on the shared host.** Free and available. Rejected because it solves
  the storage problem and creates a worse one: the data would be unreachable to
  the volunteers who need it until someone built and maintained an interface,
  and the campaign would gain a backup obligation it has no one to own.
- **SQLite on disk.** Simplest possible store, but it sits inside a directory
  that deploys replace, and it has the same no-interface problem.
- **Email only, no sheet.** Very nearly enough — the emails are the durable
  copy. Rejected because a shared inbox is a poor list: no sorting, no
  columns, and no way for two volunteers to work the same list without
  colliding.
- **Airtable.** Better as a database, comparable as a UI. Rejected on cost and
  on the campaign already living in Google Workspace.
