import { describe, expect, it } from 'vitest'
import { routes } from '../../src/lib/routes'

describe('route aliases', () => {
  it('keeps legacy html paths as aliases for extensionless routes', () => {
    const aliasByPath = new Map(routes.map((route) => [route.path, route.alias]))

    expect(aliasByPath.get('/')).toBe('/index.html')
    expect(aliasByPath.get('/meet-julia')).toBe('/meet-julia.html')
    expect(aliasByPath.get('/volunteer')).toBe('/volunteer.html')
    expect(aliasByPath.get('/secret-recipe')).toBe('/secret-recipe.html')
    expect(aliasByPath.get('/donate')).toBe('/donate.html')
  })
})
