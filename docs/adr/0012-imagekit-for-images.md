# 0012. Serve photography from ImageKit rather than the host

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

A campaign site is mostly photographs: the candidate, events, yard signs,
supporters. They arrive as full-resolution camera or phone images, they change
during the campaign, and they are the bulk of every page's weight. Half the
audience is on a phone, often on mobile data.

Doing this properly means several widths per image, modern formats with
fallbacks, and correct sizing per breakpoint. Doing it at build time is
possible, but it puts large binaries in git, lengthens every build, and makes
swapping a photo a code change plus a deploy.

Doing it badly means serving a 4MB JPEG to a phone, which on this site would be
the single largest performance problem.

## Decision

Images are stored in and served from **ImageKit** (`ik.imagekit.io/voteforjulia`),
rendered through the `@imagekit/vue` `<Image>` component, which requests
per-breakpoint transformations from their URL API. The host serves only small
static assets from `public/` — icons, the social banner, favicons.

## Consequences

- **Responsive, format-negotiated images without a build pipeline.** Width,
  quality, and format are URL parameters, so the right bytes go to each device.
- **Image bandwidth leaves the shared host**, which is the resource shared
  hosting is stingiest with, and the images come from a CDN edge rather than one
  machine.
- **The repo stays small and builds stay fast** — no binaries in git, no image
  processing step.
- **A photo can be replaced without a deploy**, which matters when a campaign
  wants a new event picture up the same evening.
- **A third-party origin on nearly every page**, so `img-src` must include
  `https://ik.imagekit.io`. It is also a dependency for above-the-fold content:
  if ImageKit is down, pages render with holes. Text and layout still work,
  because the design does not depend on images for structure.
- **Image URLs are not version-controlled content.** What is deployed no longer
  fully determines what a visitor sees, and there is no rollback for an image —
  the media library is state that lives outside the repo, alongside the Google
  Sheet ([0004](0004-no-database.md)).
- **Another account the campaign must not lose access to.**

## Alternatives considered

- **Build-time image optimization** (`vite-imagetools`, `@astrojs/image`, or a
  script). No third party, everything version-controlled, and a real rollback
  story. Rejected on the binaries-in-git and slow-build costs, and because
  updating a photo would then require a developer.
- **Hand-optimized images committed to `public/`.** Simplest, and it is what the
  handful of non-photographic assets do. Does not scale to a photo-heavy site,
  and produces one size for every device.
- **Cloudinary.** Equivalent capability. ImageKit's free tier was the better fit
  for this volume.
- **Serve originals from the host.** Free and immediate, and it would make the
  site slow on exactly the devices most voters use.
