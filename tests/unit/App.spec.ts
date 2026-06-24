import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';
import App from '../../src/App.vue';

const allRoutes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/meet-julia', component: { template: '<div />' } },
  { path: '/volunteer', component: { template: '<div />' } },
  { path: '/donate', component: { template: '<div />' } },
  { path: '/secret-recipe', component: { template: '<div />' } },
  { path: '/events', component: { template: '<div />' } }
];

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
        RouterView: true
      }
    }
  });
}

describe('App — pageHeaderTitle', () => {
  it.each([
    ['/', 'Elect Julia Hamann — A New Voice for Mankato'],
    ['/meet-julia', 'Get to Know Julia Hamann — Mankato Mayor Candidate'],
    ['/volunteer', 'Join Julia’s Team — Volunteer in Mankato'],
    ['/donate', 'Support Julia Hamann’s Campaign for Mankato Mayor'],
    ['/events', 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor'],
    ['/secret-recipe', 'Julia’s Famous Shrimp Salad Supreme Recipe']
  ])('passes the correct title for %s', async (path, expectedTitle) => {
    const wrapper = await mountAtPath(path);
    expect(wrapper.find('.header-stub').attributes('data-title')).toBe(expectedTitle);
  });
});
