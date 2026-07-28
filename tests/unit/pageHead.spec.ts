import { describe, expect, it } from 'vitest';
import { buildPageHead, campaignPersonNode, campaignWebSiteNode } from '../../src/lib/pageHead';

function metaContent(
  head: ReturnType<typeof buildPageHead>,
  key: 'name' | 'property',
  value: string
) {
  return head.meta.find((entry) => entry[key] === value)?.content;
}

function jsonLdGraph(head: ReturnType<typeof buildPageHead>) {
  const jsonLd = head.script.find((entry) => entry.type === 'application/ld+json');
  return JSON.parse(jsonLd?.textContent ?? '{}')['@graph'] as Record<string, unknown>[];
}

describe('buildPageHead', () => {
  it('builds the canonical link and og/twitter block from the shared inputs', () => {
    const head = buildPageHead({
      path: '/events',
      title: 'Events | Julia Hamann for Mankato Mayor',
      description: 'Upcoming events.'
    });

    expect(head.title).toBe('Events | Julia Hamann for Mankato Mayor');
    expect(head.link).toEqual([{ rel: 'canonical', href: 'https://voteforjulia.com/events' }]);
    expect(metaContent(head, 'name', 'description')).toBe('Upcoming events.');
    expect(metaContent(head, 'name', 'robots')).toBe('index,follow');
    expect(metaContent(head, 'property', 'og:url')).toBe('https://voteforjulia.com/events');
    expect(metaContent(head, 'property', 'og:image')).toBe(
      'https://voteforjulia.com/julia-social-banner.avif'
    );
  });

  it('maps the home path to the root canonical URL', () => {
    const head = buildPageHead({
      path: '/',
      title: 'Home | Julia Hamann for Mankato Mayor',
      description: 'Home.'
    });

    expect(head.link[0].href).toBe('https://voteforjulia.com/');
    expect(metaContent(head, 'property', 'og:url')).toBe('https://voteforjulia.com/');
  });

  it('defaults social title/description to the page title/description', () => {
    const head = buildPageHead({ path: '/x', title: 'Title', description: 'Desc' });

    expect(metaContent(head, 'property', 'og:title')).toBe('Title');
    expect(metaContent(head, 'name', 'twitter:title')).toBe('Title');
    expect(metaContent(head, 'property', 'og:description')).toBe('Desc');
    expect(metaContent(head, 'name', 'twitter:description')).toBe('Desc');
  });

  it('honors social overrides and keywords', () => {
    const head = buildPageHead({
      path: '/',
      title: 'Home | Julia Hamann for Mankato Mayor',
      socialTitle: 'Julia Hamann for Mankato Mayor',
      description: 'Meta description.',
      socialDescription: 'Social description.',
      keywords: 'a, b, c'
    });

    expect(metaContent(head, 'property', 'og:title')).toBe('Julia Hamann for Mankato Mayor');
    expect(metaContent(head, 'name', 'twitter:title')).toBe('Julia Hamann for Mankato Mayor');
    expect(metaContent(head, 'property', 'og:description')).toBe('Social description.');
    expect(metaContent(head, 'name', 'description')).toBe('Meta description.');
    expect(metaContent(head, 'name', 'keywords')).toBe('a, b, c');
  });

  it('omits the keywords meta tag when no keywords are provided', () => {
    const head = buildPageHead({ path: '/x', title: 'T', description: 'D' });

    expect(head.meta.some((entry) => entry.name === 'keywords')).toBe(false);
  });

  it('defaults the JSON-LD graph to the shared WebSite + Person nodes', () => {
    const graph = jsonLdGraph(buildPageHead({ path: '/x', title: 'T', description: 'D' }));

    expect(graph).toEqual([campaignWebSiteNode, campaignPersonNode]);
  });

  it('appends schemaNodes after the shared nodes', () => {
    const eventNode = { '@type': 'Event', name: 'Launch' };
    const graph = jsonLdGraph(
      buildPageHead({ path: '/events', title: 'T', description: 'D', schemaNodes: [eventNode] })
    );

    expect(graph).toEqual([campaignWebSiteNode, campaignPersonNode, eventNode]);
  });

  it('lets schemaGraph fully replace the graph and keeps extra scripts before the JSON-LD', () => {
    const webPageNode = { '@type': 'WebPage', name: 'Donate' };
    const head = buildPageHead({
      path: '/donate',
      title: 'T',
      description: 'D',
      scripts: [{ type: 'module', src: 'https://donorbox.org/widgets.js', async: true }],
      schemaGraph: [campaignWebSiteNode, webPageNode, campaignPersonNode]
    });

    expect(jsonLdGraph(head)).toEqual([campaignWebSiteNode, webPageNode, campaignPersonNode]);
    expect(head.script[0].src).toBe('https://donorbox.org/widgets.js');
    expect(head.script[1].type).toBe('application/ld+json');
  });

  it('appends extra meta entries', () => {
    const head = buildPageHead({
      path: '/donate',
      title: 'T',
      description: 'D',
      extraMeta: [{ property: 'og:locale', content: 'en_US' }]
    });

    expect(metaContent(head, 'property', 'og:locale')).toBe('en_US');
  });
});
