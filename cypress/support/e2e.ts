// Cypress support file — runs before every spec file.
// Add global before/after hooks or custom commands here.

// The "Action Needed" primary-election modal fires on the first load of every
// page (App.vue, gated by a sessionStorage flag) and its full-viewport backdrop
// intercepts clicks on the forms under test. Seed the dismissed flag before the
// app mounts on every cy.visit so the modal never opens during e2e runs.
// Key mirrors PRIMARY_MODAL_KEY in src/App.vue.
const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

Cypress.Commands.overwrite('visit', (originalFn, url, options) => {
  const usingOptionsObject = typeof url === 'object' && url !== null;
  const visitOptions = (
    usingOptionsObject ? url : (options ?? {})
  ) as Partial<Cypress.VisitOptions>;
  const userOnBeforeLoad = visitOptions.onBeforeLoad;

  visitOptions.onBeforeLoad = (win) => {
    win.sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
    userOnBeforeLoad?.(win);
  };

  return usingOptionsObject
    ? originalFn(visitOptions as Partial<Cypress.VisitOptions> & { url: string })
    : originalFn(url as string, visitOptions);
});
