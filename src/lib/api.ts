/**
 * Origin every form post goes to. The API is a separate host
 * ([ADR-0003](../../docs/adr/0003-separate-api-subdomain.md)), so this is
 * cross-origin by design and baked in at build time from `VITE_API_BASE_URL`.
 *
 * Exported because the form elements need it too: their `action` attributes are
 * the submit path whenever JavaScript is unavailable, and a relative action
 * would post to the static document root, which serves no API at any path.
 */
export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ||
  'https://api.voteforjulia.com';

/**
 * The message to show for a failed response.
 *
 * The API renders every error as `{"error": "..."}`, including the ones raised
 * by the framework rather than a view (`json_http_error` in api/app.py), so a
 * 404, 405 or 413 is as readable here as a validation 400. `fallback` covers
 * the cases where there is no such body to read: an empty body, HTML from
 * something in front of the app, or a blank `error` string.
 */
async function errorMessageFor(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.error === 'string' && payload.error.trim()) {
      return payload.error;
    }
  } catch {
    // Not JSON — fall through to the caller's default message.
  }

  return fallback;
}

/**
 * Posts one form to the API, rejecting with a message fit to show the user.
 *
 * Errors propagate untouched: `useFormSubmission` is what decides a failure's
 * consequences, reporting it to New Relic and putting the message on screen.
 * Catching here to log and rethrow would only duplicate that.
 */
async function postForm(
  path: string,
  formData: Record<string, string>,
  fallbackMessage: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(formData)
  });

  if (!response.ok) {
    throw new Error(await errorMessageFor(response, fallbackMessage));
  }
}

export function submitContactForm(formData: Record<string, string>): Promise<void> {
  return postForm(
    '/send-email',
    formData,
    'Unable to send your message right now. Please try again.'
  );
}

export function submitYardSignForm(formData: Record<string, string>): Promise<void> {
  return postForm(
    '/yard-sign',
    formData,
    'Unable to send your request right now. Please try again.'
  );
}
