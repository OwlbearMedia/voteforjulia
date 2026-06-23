import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitContactForm } from '../../src/lib/api';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('submitContactForm', () => {
  it('resolves on a 200 response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(null, { status: 200 }));

    await expect(
      submitContactForm({ firstName: 'Julia', email: 'julia@example.com' })
    ).resolves.toBeUndefined();
  });

  it('sends the form data as JSON to /send-email', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    await submitContactForm({ firstName: 'Julia', email: 'julia@example.com' });

    const [url, options] = fetchSpy.mock.calls[0];
    expect(String(url)).toMatch(/\/send-email$/);
    expect(options?.method).toBe('POST');
    expect(JSON.parse(options?.body as string)).toEqual({
      firstName: 'Julia',
      email: 'julia@example.com'
    });
  });

  it('throws the server error message from a non-ok JSON response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Invalid email address' }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await expect(submitContactForm({ email: 'bad' })).rejects.toThrow('Invalid email address');
  });

  it('uses the default message when a non-ok response has no error field', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'something else' }), { status: 500 })
    );

    await expect(submitContactForm({})).rejects.toThrow(
      'Unable to send your message right now. Please try again.'
    );
  });

  it('uses the default message when a non-ok response body is not valid JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('Internal Server Error', { status: 500 })
    );

    await expect(submitContactForm({})).rejects.toThrow(
      'Unable to send your message right now. Please try again.'
    );
  });

  it('uses the default message when a non-ok response body is empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(null, { status: 503 }));

    await expect(submitContactForm({})).rejects.toThrow(
      'Unable to send your message right now. Please try again.'
    );
  });

  it('rethrows a network-level fetch error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Failed to fetch'));

    await expect(submitContactForm({})).rejects.toThrow('Failed to fetch');
  });
});
