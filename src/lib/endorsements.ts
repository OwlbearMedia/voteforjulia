/**
 * The shape behind both lists on `/endorsements` — the endorsements themselves
 * and the letters of support. Both render through `JuliaEndorsementCard`.
 */
export interface Endorsement {
  name: string;
  logo: string;
  /**
   * The logo asset's own pixel size. It reserves the box before the image
   * loads, so a value copied from a differently-shaped logo jumps the page.
   */
  logoWidth: number;
  logoHeight: number;
  url: string;
  body: string[];
  links?: { label: string; url: string }[];
}

/** The candidate widths a logo is offered at, before the asset's own size caps them. */
const LOGO_WIDTHS = [240, 320, 440, 566, 728, 960, 1454];

/**
 * ImageKit's `c-at_max` never upscales, so a candidate wider than the asset
 * returns the asset unchanged while telling the browser it is larger — which
 * costs a high-DPR device the sharper choice it thought it was making. Offer
 * the widths below the asset's own, then the asset's own.
 */
export function logoBreakpoints(logoWidth: number): number[] {
  return [...LOGO_WIDTHS.filter((width) => width < logoWidth), logoWidth];
}
