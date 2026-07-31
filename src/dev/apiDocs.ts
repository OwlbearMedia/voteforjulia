/**
 * Swagger UI for api/openapi.yaml, for local use only.
 *
 * Loaded exclusively by the root `api-docs.html` entry, which Vite serves in
 * dev but never builds — so this module has no path into dist/ and adds
 * nothing to the site bundle. It lives under src/ so typecheck, ESLint and
 * Prettier cover it like the rest of the frontend.
 */
import SwaggerUIBundle from 'swagger-ui-dist/swagger-ui-bundle.js';
import 'swagger-ui-dist/swagger-ui.css';

// Resolved by Vite to a served URL; Swagger UI parses the YAML itself, so the
// spec is read straight from the file the API deploys rather than a copy that
// could drift from it.
import specUrl from '../../api/openapi.yaml?url';

/** Where `python -m api.app` listens (`PORT` overrides it there). */
const LOCAL_API_ORIGIN = 'http://localhost:5000';

/**
 * Force every "Try it out" call at the local Flask app.
 *
 * The spec lists production first, and a submission against it is not a
 * harmless read: each accepted post emails the campaign, emails the submitter,
 * and appends a row to the Google Sheet. Rewriting the origin here is stronger
 * than reordering the dropdown, which the user can change back.
 *
 * Requests already on the dev server's own origin are left alone — the spec
 * fetch is one of them, and rewriting it would break loading the page.
 */
function redirectToLocalApi(request: { url: string; [key: string]: unknown }) {
  const requested = new URL(request.url, window.location.origin);

  if (requested.origin === window.location.origin) {
    return request;
  }

  const local = new URL(LOCAL_API_ORIGIN);
  requested.protocol = local.protocol;
  requested.host = local.host;
  request.url = requested.toString();

  return request;
}

const domNode = document.getElementById('api-docs');

if (!domNode) {
  throw new Error('api-docs.html is missing its #api-docs mount point');
}

SwaggerUIBundle({
  domNode,
  url: specUrl,
  deepLinking: true,
  displayRequestDuration: true,
  // Expand the schema trees a level so field limits are visible without
  // clicking into every model.
  defaultModelsExpandDepth: 2,
  requestInterceptor: redirectToLocalApi
});
