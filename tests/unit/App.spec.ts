import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';
import App from '../../src/App.vue';

const allRoutes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/meet-julia', component: { template: '<div />' } },
  { path: '/volunteer', component: { template: '<div />' } },
  { path: '/donate', component: { template: '<div />' } },
  { path: '/secret-recipe', component: { template: '<div />' } },
  { path: '/events', component: { template: '<div />' } },
  { path: '/endorsements', component: { template: '<div />' } }
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

const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

// Lightweight stand-in for JuliaModal (tested separately) that exposes the
// `open` prop and re-creates its close()/confirm() emits — both set open false
// and fire the matching event — so we can drive App.vue's handlers.
const ModalStub = {
  props: ['open'],
  emits: ['update:open', 'confirm', 'cancel'],
  template:
    '<div class="modal-stub" :data-open="String(open)">' +
    '<button class="modal-confirm" @click="$emit(\'update:open\', false); $emit(\'confirm\')"></button>' +
    '<button class="modal-cancel" @click="$emit(\'update:open\', false); $emit(\'cancel\')"></button>' +
    '</div>'
};

async function mountWithModalStub(path = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: allRoutes });
  await router.push(path);
  await router.isReady();

  const wrapper = mount(App, {
    global: {
      plugins: [router],
      stubs: {
        JuliaHeader: true,
        JuliaFooter: true,
        RouterView: true,
        JuliaModal: ModalStub
      }
    }
  });
  // onMounted flips the ref; let the resulting re-render settle.
  await nextTick();

  return { wrapper, router };
}

describe('App — primary-election modal', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('opens the modal on mount when it has not been dismissed this session', async () => {
    const { wrapper } = await mountWithModalStub();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('true');
  });

  it('keeps the modal closed when already dismissed this session', async () => {
    sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
    const { wrapper } = await mountWithModalStub();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  it('records the dismissed flag and closes the modal on cancel', async () => {
    const { wrapper } = await mountWithModalStub();

    await wrapper.find('.modal-cancel').trigger('click');

    expect(sessionStorage.getItem(PRIMARY_MODAL_KEY)).toBe('true');
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  it('navigates to /events and records the flag on confirm', async () => {
    const { wrapper, router } = await mountWithModalStub();
    const push = vi.spyOn(router, 'push');

    await wrapper.find('.modal-confirm').trigger('click');

    expect(push).toHaveBeenCalledWith('/events');
    expect(sessionStorage.getItem(PRIMARY_MODAL_KEY)).toBe('true');
  });
});

describe('App — pageHeaderTitle', () => {
  it.each([
    ['/', 'Elect Julia Hamann — A New Voice for Mankato'],
    ['/meet-julia', 'Get to Know Julia Hamann — Mankato Mayor Candidate'],
    ['/volunteer', 'Join Julia’s Team — Volunteer in Mankato'],
    ['/donate', 'Support Julia Hamann’s Campaign for Mankato Mayor'],
    ['/events', 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor'],
    ['/endorsements', 'Endorsements for Julia Hamann — Mankato Mayor'],
    ['/secret-recipe', 'Julia’s Famous Shrimp Salad Supreme Recipe']
  ])('passes the correct title for %s', async (path, expectedTitle) => {
    const wrapper = await mountAtPath(path);
    expect(wrapper.find('.header-stub').attributes('data-title')).toBe(expectedTitle);
  });
});
