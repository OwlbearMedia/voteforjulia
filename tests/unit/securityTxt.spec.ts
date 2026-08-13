import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * `security.txt` is the one published file that goes stale on a date rather
 * than on a change, so nothing in the normal workflow would ever fail because
 * of it. RFC 9116 requires `Expires`, and a reporting scanner treats an expired
 * file as no file at all — the contact route quietly stops working while the
 * file is still sitting there looking correct.
 */
// A path rather than a file URL: the suite runs under jsdom, where
// `import.meta.url` is not a `file:` URL and `readFileSync` rejects it.
const SECURITY_TXT = readFileSync(resolve(process.cwd(), 'public/security.txt'), 'utf8');

function field(name: string): string {
  const match = SECURITY_TXT.match(new RegExp(`^${name}:\\s*(.+)$`, 'm'));
  if (!match) throw new Error(`security.txt has no ${name} field`);
  return match[1].trim();
}

describe('security.txt', () => {
  it('declares the fields RFC 9116 requires', () => {
    expect(field('Contact')).toMatch(/^mailto:.+@.+$/);
    expect(field('Canonical')).toBe('https://voteforjulia.com/.well-known/security.txt');
  });

  it('has not expired, and is renewed before it does', () => {
    const expires = new Date(field('Expires'));
    const daysLeft = (expires.getTime() - Date.now()) / 86_400_000;

    // Fails a month early on purpose. A test that only fails on the expiry date
    // tells you at the moment the file has already stopped counting.
    expect(daysLeft).toBeGreaterThan(30);
  });

  it('expires within a year, as RFC 9116 asks', () => {
    const expires = new Date(field('Expires'));
    const daysOut = (expires.getTime() - Date.now()) / 86_400_000;

    expect(daysOut).toBeLessThan(365);
  });
});
