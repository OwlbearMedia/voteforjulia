# The donate page: Donorbox + Stripe

[/donate](../src/pages/JuliaDonate.vue) embeds Donorbox's donation form. Its
architecture is not what the markup suggests, and getting it wrong shows up as
console errors on the page that takes money.

## It is not an iframe

```html
<dbox-widget campaign="julia-hamann-for-mankato-mayor" type="donation_form" />
```

`https://donorbox.org/widgets.js` (loaded via `scripts` in `buildPageHead`)
defines `dbox-widget` as a **custom element that renders into our own document**
using shadow DOM. It is not a cross-origin frame, so the donation form runs with
our origin's privileges, under our CSP, in our permissions-policy context.

It then injects **`//js.stripe.com/v3` as a top-level `<script>` in our
document**. Stripe.js in turn creates _its own_ `js.stripe.com` iframes — a
controller frame, the Payment Element, and the Apple Pay / Google Pay
availability probes.

So the real origin chain is:

```
voteforjulia.com  ──(script)──>  donorbox.org/widgets.js   (renders in-page, shadow DOM)
                  ──(script)──>  js.stripe.com/v3          (renders in-page)
                                      └─(iframes)─>  js.stripe.com  (Elements, wallet probes)
```

Not `voteforjulia.com → donorbox iframe → stripe iframe`. Assuming the latter
leads to allowlisting the wrong origins.

## What that costs us in the build

Nothing now — but it used to. While `<dbox-widget>` was a tag in the template it
had to be declared in `isCustomElement`, or Vue compiled it as a _component_
lookup and SSG emitted `<!---->` in its place: the element missing from the
prerendered HTML, appearing only after hydration, and no test catching it.

The tag now lives in a `v-html` string (see "What we do instead" below), so the
compiler never sees it. That option — and the `vue-compiler-options.ts` module
that shared it between `vite.config.ts` and `vitest.config.ts` — is gone.

What survives is the check, because a string is just as easy to typo as a tag
was to forget, and just as quiet when wrong:

```
grep dbox-widget dist/donate.html
```

## What that costs us in headers

Both security headers in [public/.htaccess](../public/.htaccess) have entries
that exist _only_ because of this widget. Neither is obvious from reading the
Vue source, so before deleting anything from them, check here.

| Directive                                         | Why                                                                         |
| ------------------------------------------------- | --------------------------------------------------------------------------- |
| `script-src donorbox.org`                         | the widget loader                                                           |
| `script-src js.stripe.com`                        | Stripe.js, injected into our document by the widget                         |
| `script-src cdn.jsdelivr.net/npm/@fingerprintjs/` | FingerprintJS, loaded by the widget for fraud detection                     |
| `script-src jspm.dev`                             | @appsignal, Donorbox's own error reporting                                  |
| `frame-src donorbox.org`                          | their reCAPTCHA frame                                                       |
| `frame-src js.stripe.com`                         | Stripe Elements / wallet frames                                             |
| `connect-src` stripe hosts                        | Stripe's API and telemetry endpoints                                        |
| `Permissions-Policy: payment`                     | `self` for Stripe.js's probes in our document, plus each frame origin below |

### The `payment` allowlist

```
payment=(self "https://donorbox.org" "https://js.stripe.com")
```

Every origin that runs a frame needing the Payment Request API has to be named
here **and** the frame element needs `allow="payment"` (Stripe.js sets that on
its own frames). Miss an origin and the console logs, once per affected frame:

```
[Violation] Permissions policy violation: payment is not allowed in this document.
```

**This fails quietly.** Card donations keep working — only the express-checkout
path (Apple Pay / Google Pay) is suppressed, and Stripe falls back to the normal
card form. So an empty violation count is worth chasing: the errors mean wallet
payments are silently unavailable, not merely that the console is noisy.

Note the syntax trap: allowlist origins must be **quoted strings** (only
`self`/`src`/`*`/`none` are bare tokens), and the quoting has to survive
LiteSpeed — see [hosting.md](hosting.md).

## Diagnosing a violation

1. Read the exact wording — the three messages mean different things:
   - _Invalid allowlist item_ — the header parsed, but one entry was rejected
     and dropped (usually an unquoted origin).
   - _Parse of permissions policy failed_ — malformed badly enough that **the
     whole header is discarded**, so `geolocation`/`microphone`/`camera` stop
     being restricted too. Worse than having no fix at all.
   - _Permissions policy violation_ — the header is fine; an origin is genuinely
     missing from the allowlist.
2. Confirm what is actually being served — do not trust the repo or a local
   Apache:
   ```
   curl -sI https://test.voteforjulia.com/donate | grep -i permissions-policy
   ```
3. If the header is correct, attribute the violation to a frame: DevTools →
   Application → Frames → select the frame → **Permissions Policy**, which names
   the denied feature and the reason. Add that frame's origin to the allowlist
   (and check `frame-src` permits it, or you will get a CSP error too).

## Widget internals worth knowing

`widgets.js` is only a loader; it dynamically imports a hashed per-widget module
(`donorbox.org/assets/widgets/donation_form-<hash>.js`). The hash changes when
Donorbox ships, which is why `script-src` allows the `donorbox.org` origin
rather than specific files, and why `jspm.dev` cannot be path-scoped — its
module graph imports version-pinned internal paths that move.

## Their constructor throws when Vue creates the element

Donorbox's constructor sets attributes on itself. That is legal when the browser
_upgrades_ an element that already exists, and illegal on
`document.createElement`, which the custom-elements spec requires to reject a
constructor that gave itself attributes. So the same element boots fine one way
and blows up the other, twice:

```
TypeError: Cannot convert undefined or null to object
    at DboxWidget.attributeChangedCallback (https://donorbox.org/widgets.js:146:12)
    at DboxWidget.setDefaultAttributes (…:169:41)
    at new DboxWidget (…:100:10)
    at createElement (…/assets/app-<hash>.js)   ← Vue
NotSupportedError: Failed to execute 'createElement' on 'Document': The result must not have attributes
```

Both come from Donorbox's code, and there is no version to pin (see the hashed
module above). What this repo controls is which path the element is created on,
and whether the widget can boot before Vue has finished hydrating.

### How it used to fire

`widgets.js` was loaded as `async type="module"` from `<head>`, so it raced
hydration on an ordinary page load:

1. The script won the race and ran `customElements.define('dbox-widget', …)`.
2. That upgraded the prerendered element in place — shadow root attached,
   attributes rewritten.
3. Vue then hydrated, found DOM it had not rendered, discarded the element and
   mounted a fresh one via `document.createElement`.
4. The tag was defined by now, so the constructor ran on the forbidden path and
   the visitor got the donate page **with no donation form**.

Lose the race the other way and everything worked, which is what made it
intermittent, and why a cold cache — CI, or a first visit on mobile data — made
it more likely. The same crash hit a second SPA visit to `/donate`, where
`define` had already run and Vue mounted the tag from scratch.

### What we do instead

Two changes in [JuliaDonate.vue](../src/pages/JuliaDonate.vue), both load-bearing:

- **The markup is a string rendered with `v-html`**, not a tag in the template.
  Assigning `innerHTML` parses a fragment, and fragment parsing always defers
  custom elements to the upgrade path, so the vendor constructor never runs
  under `createElement`'s no-attributes rule. It also puts the widget outside
  Vue's vdom, so the shadow root and the Stripe scripts it injects cannot
  register as a hydration mismatch. This is the half that covers SPA
  navigation.
- **The loader is appended in `onMounted`**, not emitted into `<head>`. The
  prerendered element stays a plain, un-upgraded tag until Vue is done with it.
  A `modulepreload` link keeps the download early, so only execution moved.

The invariant to preserve: **nothing may define `dbox-widget` before hydration
finishes, and Vue must never render the tag itself.** New Relic is where to
check whether real traffic still hits it — search the two messages above.

### Where it showed up in CI

An uncaught app exception fails a Cypress test, so `cypress/e2e/donate.cy.ts`
used to lose its first attempt on most runs. That was invisible in the summary,
because `retries.runMode: 1` passes the test on the retry. The tell was a run
that reported `1 passing` and still wrote a `(failed).png` screenshot.

That should be gone now. If it returns, do not read it as flaky infrastructure,
and do not paper over it by widening retries or by suppressing the error in
`uncaught:exception` — that would hide the visitor-facing half. Check the
invariant above instead.
