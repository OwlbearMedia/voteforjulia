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

## What that costs us in the compiler

`dbox-widget` must be declared in
[vue-compiler-options.ts](../vue-compiler-options.ts), or Vue compiles it as a
component lookup that fails and SSG emits `<!---->` in its place. See the
"Custom elements" section of [CLAUDE.md](../CLAUDE.md).

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
