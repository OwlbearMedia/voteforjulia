import { describe, expect, it } from 'vitest';
import { appRoutePaths } from '../../src/lib/routePaths';
import { routes } from '../../src/lib/routes';

describe('routes', () => {
  it('uses extensionless client routes and no legacy html aliases', () => {
    const paths = routes.map((route) => route.path);

    expect(paths).toEqual([...appRoutePaths]);
    expect(paths.every((path) => !path.endsWith('.html'))).toBe(true);
  });
});
