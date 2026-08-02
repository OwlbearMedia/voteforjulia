describe('Donate page', () => {
  it('loads the Donorbox widget', () => {
    cy.visit('/donate');

    cy.get('dbox-widget', { timeout: 15000 }).should('be.visible');
  });

  // The first visit runs customElements.define. Coming back without a reload is
  // therefore the case where Vue would mount <dbox-widget> against an already
  // registered tag — which used to throw NotSupportedError out of Donorbox's
  // constructor and leave the page with no donation form. Cypress fails on any
  // uncaught app exception, so the assertion is partly the absence of one.
  // See docs/donate-integration.md.
  it('still renders the widget on a return visit within the same session', () => {
    cy.visit('/donate');
    cy.get('dbox-widget', { timeout: 15000 }).should('be.visible');

    cy.get('a[href="/volunteer"]').filter(':visible').first().click();
    cy.location('pathname').should('eq', '/volunteer');
    cy.get('dbox-widget').should('not.exist');

    cy.get('a[href="/donate"]').filter(':visible').first().click();
    cy.location('pathname').should('eq', '/donate');
    cy.get('dbox-widget', { timeout: 15000 }).should('be.visible');
  });
});
