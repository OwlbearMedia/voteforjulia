# 0005. Outsource donations to Donorbox and Stripe

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The campaign needs to accept contributions online. Political contributions carry
requirements ordinary e-commerce does not: contributor name, address, employer
and occupation have to be collected and reported, contribution limits apply, and
the treasurer needs an export that reconciles with what gets filed.

Handling card details in our own page would put the site in PCI DSS scope. On a
shared host, with one developer, for a three-month campaign, that is not a
trade anyone should make.

## Decision

Embed **Donorbox** on `/donate`, which processes through **Stripe**. No payment
data touches our origin's code, our API, or our host. The API has no donation
endpoint at all; the donate page is otherwise a normal prerendered page.

## Consequences

- **PCI scope stays with Stripe and Donorbox.** Our code never sees a card
  number, and there is no payment state to store, reconcile, or leak.
- **The treasurer gets contributor fields and exports out of the box**,
  including the employer/occupation fields political giving needs, without any
  of it being modelled in this repo.
- **We pay a processing fee per contribution.** The alternative was building and
  maintaining the compliance surface ourselves; the fee is cheaper than one
  evening of that.
- **The widget is not an iframe, and that costs us at the edge.** Donorbox's
  `<dbox-widget>` is a custom element rendering into _our_ document, which then
  injects Stripe.js as a top-level script in our page. So the donation flow runs
  under our CSP and our Permissions-Policy, and both headers carry entries that
  exist solely for it — including a `jspm.dev` script source that cannot be
  usefully path-scoped. The full origin chain and every header entry it forces is
  in [../donate-integration.md](../donate-integration.md).
- **The build has to know about their tag.** `dbox-widget` must be declared in
  `isCustomElement`, or SSG emits `<!---->` and the donation form is missing
  from the prerendered page ([0002](0002-static-site-generation.md)).
- **Their bugs are our test failures.** The vendor constructor throws when Vue
  creates the element, which fails `donate.cy.ts`'s first attempt on most runs
  and is absorbed by a Cypress retry.
- **The donation experience is theirs to change.** Styling is limited to what
  the widget exposes, and a vendor change can alter the page without a deploy.

> **Amended 2026-08-02.** The third and fourth consequences above no longer hold
> as written. The widget is now rendered as raw markup through `v-html` and its
> loader runs from `onMounted`, so Vue never constructs the element: the vendor
> crash is fixed for visitors as well as for CI, and `isCustomElement` has been
> removed along with the `vue-compiler-options.ts` module. The decision to
> outsource donations is unchanged — see
> [../donate-integration.md](../donate-integration.md).

## Alternatives considered

- **Stripe Checkout directly, plus our own contributor fields.** Fewer vendors
  and a cleaner page, but it puts the compliance fields, the limit checks, and
  the treasurer's export on us to build and keep correct. That is the actual
  work in political fundraising; the card charge is the easy part.
- **ActBlue.** The obvious answer for federal Democratic campaigns and a strong
  one, but oriented to that ecosystem; Donorbox fit a nonpartisan municipal race
  better.
- **Link out to a hosted donation page.** Zero integration and zero CSP
  entanglement, at the cost of a full-page hand-off to another domain on the
  page whose conversion rate matters most. Rejected on that alone.
