/**
 * Keeps the tracking checkboxes attached to the live rows of each worksheet,
 * however a row arrives — the API's `values.append`, a volunteer inserting a
 * row, or a volunteer typing into a blank one.
 *
 * ## Why this exists rather than a pre-filled column
 *
 * The obvious way to get a checkbox on every future row is to apply the
 * validation down the whole column. Doing that broke the yard-sign form for
 * four days in August 2026: a checkbox cell reads `FALSE` rather than empty, so
 * a pre-filled column is *data* as far as the Sheets API is concerned. The API
 * appends after the last row of the detected table, that table stretched to row
 * 963, and submissions landed there — below anything a human scrolls to, while
 * the endpoint returned 200 and the submitter got their confirmation email. See
 * docs/architecture.md.
 *
 * So the rule this file enforces is narrow and load-bearing:
 *
 *   **A checkbox exists on a row if and only if that row holds a submission.**
 *
 * Not "every row down to the last one used" — a volunteer who types into row
 * 100 and leaves 29–99 empty would otherwise get 71 rows of `FALSE` and
 * recreate the outage. Liveness is decided per row, from the submission columns
 * themselves.
 *
 * ## What the API does not need this for
 *
 * `values.append` uses `insertDataOption=INSERT_ROWS`, and an inserted row
 * inherits validation from the row above it. Verified on 2026-08-06: an append
 * onto a clean sheet landed at row 29 and came back with `Paid` and `Delivered`
 * already set to `BOOLEAN`. Form submissions are covered without this script.
 * What is not covered, and what this is for, is a human typing into a blank row
 * — no row is inserted, so there is nothing to inherit from.
 *
 * ## Installing it
 *
 * Extensions → Apps Script, paste this in, then add an *installable* trigger:
 * Triggers → Add Trigger → `onSheetChange` / From spreadsheet / On change.
 *
 * The installable trigger is not optional. The simple `onEdit(e)` trigger does
 * not fire for writes made through the Sheets API.
 *
 * ## This file drifts
 *
 * It is the checked-in copy; the running copy lives in the spreadsheet and
 * nothing syncs them. Same deal as monitoring/ — edit it there, commit it here,
 * or the next person reads a stale script.
 */

/**
 * Which columns carry checkboxes, by worksheet title. Titles must match the tab
 * names exactly; those are also what the API writes to (`GOOGLE_SHEETS_WORKSHEET`
 * and `GOOGLE_SHEETS_YARDSIGN_WORKSHEET`).
 *
 * Yard Signs is `Date | First Name | Last Name | Email | Phone | Address |
 * Payment Method | Paid | Delivered | Notes`. A–G are the submission, written by
 * the API — never list those. H and I are the checkboxes. **J is Notes, free
 * text, and must stay off this list**; checkbox validation there would reject
 * every note anyone writes.
 */
const CHECKBOX_COLUMNS = {
  'Yard Signs': ['H', 'I']
};

/** First row of data. Row 1 is the header and never gets a checkbox. */
const FIRST_DATA_ROW = 2;

/**
 * Change types worth reacting to. Deliberately excludes FORMAT and OTHER, which
 * is what this script's own validation writes report back as — reacting to
 * those would make it re-trigger itself.
 */
const HANDLED_CHANGE_TYPES = ['INSERT_ROW', 'EDIT', 'PASTE', 'INSERT_GRID'];

function onSheetChange(event) {
  if (event && event.changeType && HANDLED_CHANGE_TYPES.indexOf(event.changeType) === -1) {
    return;
  }

  syncCheckboxValidation();
}

/**
 * Bring every configured worksheet's checkbox columns in line with its data.
 *
 * Safe to run by hand from the Apps Script editor, which is also how to repair
 * a sheet after a bulk import or a checkbox range dragged too far down. It is
 * idempotent, and it writes nothing when nothing needs changing — which is also
 * what stops it from re-triggering itself indefinitely.
 */
function syncCheckboxValidation() {
  const spreadsheet = SpreadsheetApp.getActive();

  Object.keys(CHECKBOX_COLUMNS).forEach(function (title) {
    const sheet = spreadsheet.getSheetByName(title);
    if (!sheet) {
      // A renamed or deleted tab is a configuration problem, not a reason to
      // abandon the other worksheets in the same run.
      console.warn('No worksheet named "' + title + '"; skipping.');
      return;
    }

    syncSheet(sheet, CHECKBOX_COLUMNS[title]);
  });
}

function syncSheet(sheet, columnLetters) {
  const checkbox = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  const columns = columnLetters.map(columnLetterToIndex);
  const lastRow = sheet.getLastRow();
  const maxRows = sheet.getMaxRows();

  // Anything below the last used row must carry neither value nor validation,
  // or it reads as FALSE and stretches the table the API appends to.
  if (maxRows > lastRow) {
    columns.forEach(function (column) {
      const range = sheet.getRange(lastRow + 1, column, maxRows - lastRow, 1);
      range.clearDataValidations();
      range.clearContent();
    });
  }

  if (lastRow < FIRST_DATA_ROW) {
    return;
  }

  const height = lastRow - FIRST_DATA_ROW + 1;
  const width = sheet.getLastColumn();
  const data = sheet.getRange(FIRST_DATA_ROW, 1, height, width).getValues();

  columns.forEach(function (column) {
    const range = sheet.getRange(FIRST_DATA_ROW, column, height, 1);
    const existingRules = range.getDataValidations();
    const existingValues = range.getValues();

    const rules = [];
    const values = [];
    let changed = false;

    for (let offset = 0; offset < height; offset++) {
      const live = isSubmissionRow(data[offset], columns);
      const hasRule = existingRules[offset][0] !== null;

      rules.push([live ? checkbox : null]);
      // An empty row keeps no value either: clearing the checkbox but leaving
      // the FALSE behind is exactly the state that caused the outage.
      values.push([live ? existingValues[offset][0] : '']);

      if (live !== hasRule || (!live && existingValues[offset][0] !== '')) {
        changed = true;
      }
    }

    // Writing unconditionally would fire another change event on every pass.
    // The run that follows one of this script's own writes finds nothing to do
    // and stops here.
    if (!changed) {
      return;
    }

    range.setDataValidations(rules);
    range.setValues(values);
  });
}

/**
 * Does this row hold a submission?
 *
 * Every column except the checkbox ones counts, so a row someone started by
 * typing only a name, or only a note, is still a real row. The checkbox columns
 * are excluded deliberately: letting them vote would make a stray `FALSE` argue
 * for its own existence, which is the loop this whole file exists to break.
 */
function isSubmissionRow(row, checkboxColumns) {
  for (let index = 0; index < row.length; index++) {
    if (checkboxColumns.indexOf(index + 1) !== -1) {
      continue;
    }
    if (row[index] !== '' && row[index] !== null && row[index] !== undefined) {
      return true;
    }
  }

  return false;
}

function columnLetterToIndex(letter) {
  let index = 0;
  for (let position = 0; position < letter.length; position++) {
    index = index * 26 + (letter.toUpperCase().charCodeAt(position) - 64);
  }

  return index;
}
