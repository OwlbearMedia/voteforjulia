// Use a timestamp-suffixed email so each run creates a unique sheet row.
const TEST_EMAIL = `cypress-test+${Date.now()}@example.com`;
const TEST_FIRST_NAME = 'Cypress';
const TEST_LAST_NAME = 'AutoTest';
const TEST_ADDRESS = '123 Main St, Mankato, MN 56001';
const YARD_SIGN_WORKSHEET = 'Yard Signs';

type SheetRow = { rowIndex: number; row: string[] };

describe('Yard sign form', () => {
  // Track the sheet row so the after() hook can clean it up even on failure.
  let sheetRowIndex: number | null = null;

  after(() => {
    if (sheetRowIndex !== null) {
      cy.task('deleteSheetRow', { rowIndex: sheetRowIndex, worksheet: YARD_SIGN_WORKSHEET });
    }
  });

  it('submits successfully and records the entry in Google Sheets', () => {
    cy.visit('/yard-signs');

    cy.get('#yard-sign-first-name').type(TEST_FIRST_NAME);
    cy.get('#yard-sign-last-name').type(TEST_LAST_NAME);
    cy.get('#yard-sign-email').type(TEST_EMAIL);
    cy.get('#yard-sign-phone').type('5551234567');
    cy.get('#yard-sign-address').type(TEST_ADDRESS);

    cy.get('button[type="submit"]').click();

    // The API returns 200 only after the sheet row is written, so by the time
    // the success message renders the row is guaranteed to exist.
    cy.contains(`Thanks so much for your support, ${TEST_FIRST_NAME}!`, {
      timeout: 15000
    }).should('be.visible');

    cy.task<SheetRow | null>(
      'findSheetRow',
      { email: TEST_EMAIL, worksheet: YARD_SIGN_WORKSHEET },
      { timeout: 30000 }
    ).then((result) => {
      expect(result, 'Sheet row should exist after successful submission').to.not.equal(null);

      const { rowIndex, row } = result!;
      // Column layout: [timestamp, firstName, lastName, email, phone, address]
      expect(row[1]).to.equal(TEST_FIRST_NAME);
      expect(row[2]).to.equal(TEST_LAST_NAME);
      expect(row[3]).to.equal(TEST_EMAIL);
      expect(row[5]).to.equal(TEST_ADDRESS);

      sheetRowIndex = rowIndex;
    });
  });
});
