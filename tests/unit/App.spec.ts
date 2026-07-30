import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
        RouterView: true
      }
    }
  });
}

const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

// Mirrors PRIMARY_MODAL_EXPIRES_AT in App.vue: midnight CDT at the end of
// primary election day. Tests pin the clock relative to it so they neither
// depend on nor expire with the real date.
const PRIMARY_MODAL_EXPIRES_AT = Date.parse('2026-08-12T05:00:00Z');
const BEFORE_PRIMARY = PRIMARY_MODAL_EXPIRES_AT - 24 * 60 * 60 * 1000;

// Lightweight stand-in for JuliaModal (tested separately) that exposes the
// `open` prop and re-creates its close() emit — sets open false and fires
// `cancel` — so we can drive App.vue's handler. The real modal only renders a
// confirm button when given a `confirmLabel`, which App.vue does not pass, so
// the stub deliberately has no confirm affordance either.
const ModalStub = {
  props: ['open'],
  emits: ['update:open', 'cancel'],
  template:
    '<div class="modal-stub" :data-open="String(open)">' +
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
    vi.useFakeTimers();
    vi.setSystemTime(BEFORE_PRIMARY);
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it('never opens the modal once the primary is over', async () => {
    vi.setSystemTime(PRIMARY_MODAL_EXPIRES_AT);
    const { wrapper } = await mountWithModalStub();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  it('records the dismissed flag and closes the modal on cancel', async () => {
    const { wrapper } = await mountWithModalStub();

    await wrapper.find('.modal-cancel').trigger('click');

    expect(sessionStorage.getItem(PRIMARY_MODAL_KEY)).toBe('true');
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });
});

// Expected <h1> per route. Kept explicit (the point is to assert the literal
// strings), with the completeness check below standing in for derivation.
const expectedHeaderTitles: [string, string][] = [
  ['/', 'Elect Julia Hamann — A New Voice for Mankato'],
  ['/meet-julia', 'Get to Know Julia Hamann — Mankato Mayor Candidate'],
  ['/volunteer', 'Join Julia’s Team — Volunteer in Mankato'],
  ['/donate', 'Support Julia Hamann’s Campaign for Mankato Mayor'],
  ['/events', 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor'],
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
