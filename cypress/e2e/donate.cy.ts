describe('Donate page', () => {
  it('loads the Donorbox widget', () => {
    cy.visit('/donate');

    cy.get('dbox-widget', { timeout: 15000 }).should('be.visible');
  });
});
