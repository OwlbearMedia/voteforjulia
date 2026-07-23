describe('Donate page', () => {
  it('loads the Donorbox donation iframe', () => {
    cy.visit('/donate');

    cy.get('iframe.donorbox-embed', { timeout: 15000 })
      .should('be.visible')
      .and('have.attr', 'src', 'https://donorbox.org/embed/julia-hamann-for-mankato-mayor');
  });
});
