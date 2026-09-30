import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import JuliaVideo from '../../src/components/JuliaVideo.vue';

// The origin itself is covered by embedOrigins.spec.ts, against frame-src.
describe('JuliaVideo', () => {
  const player = mount(JuliaVideo, {
    props: { videoId: 'bc4dvZpAa-A', title: 'Julia Hamann on reimagining public safety' }
  }).find('iframe');

  it('embeds the given video under the given title', () => {
    expect(player.attributes('src')).toBe('https://www.youtube-nocookie.com/embed/bc4dvZpAa-A');
    expect(player.attributes('title')).toBe('Julia Hamann on reimagining public safety');
  });

  it('stays out of the initial page load', () => {
    expect(player.attributes('loading')).toBe('lazy');
  });
});
