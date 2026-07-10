// Use a timestamp-suffixed email so each run creates a unique sheet row.
const TEST_EMAIL = `cypress-test+${Date.now()}@example.com`;
const TEST_FIRST_NAME = 'Cypress';
const TEST_LAST_NAME = 'AutoTest';

type SheetRow = { rowIndex: number; row: string[] };

describe('Volunteer form', () => {
  // Track the sheet row so the after() hook can clean it up even on failure.
  let sheetRowIndex: number | null = null;

  after(() => {
    if (sheetRowIndex !== null) {
      cy.task('deleteSheetRow', { rowIndex: sheetRowIndex });
    }
  });

  it('submits successfully and records the entry in Google Sheets', () => {
    cy.visit('/volunteer');

    cy.get('#contact-first-name').type(TEST_FIRST_NAME);
    cy.get('#contact-last-name').type(TEST_LAST_NAME);
    cy.get('#contact-email').type(TEST_EMAIL);
    cy.get('#contact-phone').type('5551234567');
    cy.get('#help-canvassing').check();
    cy.get('#contact-message').type('Automated Cypress test — safe to delete.');

    cy.get('button[type="submit"]').click();

    // The API returns 200 only after two blocking SMTP sends (notification +
    // confirmation) and a Sheets API append complete, so give this real
    // headroom — a generous timeout here is cheap, a flaky failure isn't.
    cy.contains(`Thanks so much for your support, ${TEST_FIRST_NAME}!`, {
      timeout: 30000
    }).should('be.visible');

    cy.task<SheetRow | null>('findSheetRow', { email: TEST_EMAIL }, { timeout: 45000 }).then(
      (result) => {
        expect(result, 'Sheet row should exist after successful submission').to.not.equal(null);

        const { rowIndex, row } = result!;
        // Column layout: [timestamp, firstName, lastName, email, phone, helpWays, message]
        expect(row[1]).to.equal(TEST_FIRST_NAME);
        expect(row[2]).to.equal(TEST_LAST_NAME);
        expect(row[3]).to.equal(TEST_EMAIL);
        expect(row[5]).to.equal('Canvassing');

        sheetRowIndex = rowIndex;
      }
    );
  });
});
