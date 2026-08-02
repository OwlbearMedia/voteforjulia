/**
 * Shared <head> builder for page components.
 *
 * Every page repeats the same canonical link plus a ~60-line og/twitter/robots
 * block that differs only by title, description, and URL — and almost every page
 * embeds the same WebSite + Person JSON-LD nodes. `buildPageHead` generates all
 * of that from a few inputs; pages pass overrides for the parts that vary
 * (bare social title, keywords, extra JSON-LD nodes, third-party scripts, extra
 * meta tags). Feed the result straight to `useHead`.
 */

const SITE_URL = 'https://voteforjulia.com';
const SOCIAL_BANNER = `${SITE_URL}/julia-social-banner.avif`;
const SOCIAL_IMAGE_ALT = 'Julia Hamann for Mankato Mayor campaign logo';

type JsonLdNode = Record<string, unknown>;

// The `data-*` index signature mirrors unhead's own tag types so these arrays
// are assignable to `useHead` when stored in a variable (object literals are
// exempt from the missing-index-signature check, but named types are not).
interface HeadMeta {
  name?: string;
  property?: string;
  content: string;
  [key: `data-${string}`]: string;
}

interface HeadScript {
  type?: string;
  src?: string;
  async?: boolean;
  textContent?: string;
  [key: `data-${string}`]: string;
}

interface HeadLink {
  rel: string;
  href: string;
  [key: `data-${string}`]: string;
}

export interface PageHeadOptions {
  /** Canonical path, e.g. `/donate` (use `/` for home). Drives canonical + og:url. */
  path: string;
  /** Full document <title> and the default social (og/twitter) title. */
  title: string;
  /** Meta description and the default social (og/twitter) description. */
  description: string;
  /** Override the og/twitter title when it should differ from `title`. */
  socialTitle?: string;
  /** Override the og/twitter description when it should differ from `description`. */
  socialDescription?: string;
  /** Optional keywords meta tag. */
  keywords?: string;
  /**
   * JSON-LD `@graph` nodes appended after the shared WebSite + Person nodes.
   * Use for page-specific schema such as Event entries.
   */
  schemaNodes?: JsonLdNode[];
  /**
   * Fully replace the JSON-LD `@graph` (rare — only when node ordering matters,
   * e.g. inserting a WebPage node between WebSite and Person). Compose it from
   * the exported `campaignWebSiteNode` / `campaignPersonNode` constants.
   * Takes precedence over `schemaNodes`.
   */
  schemaGraph?: JsonLdNode[];
  /** Extra <script> entries (e.g. a third-party widget loader). */
  scripts?: HeadScript[];
  /**
   * Extra <link> entries appended after the canonical link — e.g. a
   * `modulepreload` that warms a third-party script the page executes itself
   * after hydration.
   */
  extraLinks?: HeadLink[];
  /** Extra <meta> entries appended after the standard block. */
  extraMeta?: HeadMeta[];
}

/** WebSite node shared by every page that emits JSON-LD. */
export const campaignWebSiteNode: JsonLdNode = {
  '@type': 'WebSite',
  name: 'Vote for Julia Hamann',
  url: `${SITE_URL}/`
};

/** Person node describing the candidate, shared by every page that emits JSON-LD. */
export const campaignPersonNode: JsonLdNode = {
  '@type': 'Person',
  name: 'Julia Hamann',
  url: `${SITE_URL}/`,
  jobTitle: 'Candidate for Mayor of Mankato',
  description: 'Campaign website for Julia Hamann running for Mayor of Mankato.',
  address: {
    '@type': 'PostalAddress',
    addressLocality: 'Mankato',
    addressRegion: 'MN',
    addressCountry: 'US'
  },
  areaServed: {
    '@type': 'City',
    name: 'Mankato'
  },
  knowsAbout: [
    'Environmental justice',
    'Government transparency',
    'Affordable housing',
    'Community-led safety'
  ],
  sameAs: [
    'https://www.facebook.com/profile.php?id=61590411090366',
    'https://www.instagram.com/voteforjuliahamann/'
  ]
};

export function buildPageHead(options: PageHeadOptions) {
  const {
    path,
    title,
    description,
    socialTitle = title,
    socialDescription = description,
    keywords,
    schemaNodes = [],
    schemaGraph,
    scripts = [],
    extraLinks = [],
    extraMeta = []
  } = options;

  const url = `${SITE_URL}${path}`;
  const graph = schemaGraph ?? [campaignWebSiteNode, campaignPersonNode, ...schemaNodes];

  const script: HeadScript[] = [
    ...scripts,
    {
      type: 'application/ld+json',
      textContent: JSON.stringify({ '@context': 'https://schema.org', '@graph': graph })
    }
  ];

  const meta: HeadMeta[] = [
    { name: 'description', content: description },
    ...(keywords ? [{ name: 'keywords', content: keywords }] : []),
    { name: 'robots', content: 'index,follow' },
    { property: 'og:type', content: 'website' },
    { property: 'og:site_name', content: 'Vote for Julia' },
    { property: 'og:title', content: socialTitle },
    { property: 'og:description', content: socialDescription },
    { property: 'og:url', content: url },
    { property: 'og:image', content: SOCIAL_BANNER },
    { property: 'og:image:width', content: '1200' },
    { property: 'og:image:height', content: '583' },
    { property: 'og:image:alt', content: SOCIAL_IMAGE_ALT },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:title', content: socialTitle },
    { name: 'twitter:description', content: socialDescription },
    { name: 'twitter:image', content: SOCIAL_BANNER },
    { name: 'twitter:image:alt', content: SOCIAL_IMAGE_ALT },
    ...extraMeta
  ];

  const link: HeadLink[] = [{ rel: 'canonical', href: url }, ...extraLinks];

  return {
    title,
    link,
    script,
    meta
  };
}
