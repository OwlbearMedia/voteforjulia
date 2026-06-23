import { describe, expect, it } from 'vitest';
import { routes } from '../../src/lib/routes';

describe('routes', () => {
  it('uses extensionless client routes and no legacy html aliases', () => {
    const paths = routes.map((route) => route.path);

    expect(paths).toEqual(['/', '/meet-julia', '/volunteer', '/secret-recipe', '/donate', '/events']);
    expect(paths.every((path) => !path.endsWith('.html'))).toBe(true);
  });
});
