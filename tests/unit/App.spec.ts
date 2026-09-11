import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';
import App from '../../src/App.vue';
import { appRoutePaths } from '../../src/lib/routePaths';

// Derived from the canonical path list rather than hand-maintained, so a newly
// added page can't silently go untested here (which is how /yard-signs was
// missed).
const allRoutes = appRoutePaths.map((path) => ({
  path,
  component: { template: '<div />' }
}));

async function mountAtPath(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: allRoutes });
  await router.push(path);
  await router.isReady();

  return mount(App, {
    global: {
      plugins: [router],
      stubs: {
        JuliaHeader: {
          props: ['title'],
          template: '<div class="header-stub" :data-title="title" />'
        },
        JuliaFooter: true,
        RouterView: true,
        JuliaPrimaryModal: true
      }
    }
  });
}

// Expected <h1> per route. Kept explicit (the point is to assert the literal
// strings), with the completeness check below standing in for derivation.
const expectedHeaderTitles: [string, string][] = [
  ['/', 'Elect Julia Hamann — A New Voice for Mankato'],
  ['/meet-julia', 'Get to Know Julia Hamann — Mankato Mayor Candidate'],
  ['/volunteer', 'Join Julia’s Team — Volunteer in Mankato'],
  ['/donate', 'Support Julia Hamann’s Campaign for Mankato Mayor'],
  ['/events', 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor'],
  ['/news', 'Julia Hamann in the News — Coverage of the Mankato Mayor Race'],
  ['/endorsements', 'Endorsements for Julia Hamann — Mankato Mayor'],
  ['/secret-recipe', 'Julia’s Famous Shrimp Salad Supreme Recipe'],
  ['/yard-signs', 'Get a Yard Sign — Julia Hamann for Mankato Mayor']
];

describe('App — pageHeaderTitle', () => {
  it('asserts a title for every canonical route', () => {
    expect(expectedHeaderTitles.map(([path]) => path).sort()).toEqual([...appRoutePaths].sort());
  });

  it.each(expectedHeaderTitles)('passes the correct title for %s', async (path, expectedTitle) => {
    const wrapper = await mountAtPath(path);
    expect(wrapper.find('.header-stub').attributes('data-title')).toBe(expectedTitle);
  });
});
