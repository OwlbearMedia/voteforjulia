describe('Donate page', () => {
  it('includes the Donorbox widget', () => {
    cy.intercept('GET', 'https://donorbox.org/widgets.js', { body: '' });

    cy.visit('/donate');

    cy.get('dbox-widget')
      .should('exist')
      .and('have.attr', 'campaign', 'julia-hamann-for-mankato-mayor');
  });
});
