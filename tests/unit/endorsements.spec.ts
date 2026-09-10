import { describe, expect, it } from 'vitest';
import { logoBreakpoints } from '../../src/lib/endorsements';

/**
 * The srcset candidates a logo is offered at. ImageKit's `c-at_max` never
 * upscales, so a candidate above the asset's own width returns the asset
 * unchanged while claiming to be wider — the browser then picks it on a
 * high-DPR screen and renders it soft. Every case below is a real asset on
 * `/endorsements` except the boundary ones.
 */
describe('logoBreakpoints', () => {
  it.each([
    // asset width, expected candidates
    [960, [240, 320, 440, 566, 728, 960]], // indivisible.png
    [447, [240, 320, 440, 447]], // nasw-mn.jpeg
    [429, [240, 320, 429]], // mn-dfl-logo.svg
    [400, [240, 320, 400]], // run-for-something.jpg
    [1454, [240, 320, 440, 566, 728, 960, 1454]], // the widest standard step
    [2000, [240, 320, 440, 566, 728, 960, 1454, 2000]], // wider than every step
    [240, [240]], // equal to the narrowest step, not doubled
    [100, [100]] // narrower than every step
  ])('offers %i as %j', (logoWidth, expected) => {
    expect(logoBreakpoints(logoWidth)).toEqual(expected);
  });

  it('never offers a candidate wider than the asset', () => {
    for (const width of [100, 240, 400, 429, 447, 960, 1454, 2000]) {
      expect(Math.max(...logoBreakpoints(width))).toBeLessThanOrEqual(width);
    }
  });
});
