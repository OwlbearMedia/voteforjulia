import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import JuliaPrimaryModal from '../../src/components/JuliaPrimaryModal.vue';

const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

// Mirrors JuliaPrimaryModal.vue: midnight CDT at the start of primary election
// day, with the modal retiring 24 hours later. Tests pin the clock relative to
// these so they neither depend on nor expire with the real date.
const DAY_MS = 24 * 60 * 60 * 1000;
const PRIMARY_DAY_STARTS_AT = Date.parse('2026-08-11T05:00:00Z');
const PRIMARY_MODAL_EXPIRES_AT = PRIMARY_DAY_STARTS_AT + DAY_MS;

// Lightweight stand-in for JuliaModal (tested separately) that exposes the
// `open` prop and re-creates its close() emit — sets open false and fires
// `cancel` — so we can drive the dismissal handler. The real modal only renders
// a confirm button when given a `confirmLabel`, which this component does not
// pass, so the stub deliberately has no confirm affordance either.
const ModalStub = {
  props: ['open'],
  emits: ['update:open', 'cancel'],
  template:
    '<div class="modal-stub" :data-open="String(open)">' +
    '<slot />' +
    '<button class="modal-cancel" @click="$emit(\'update:open\', false); $emit(\'cancel\')"></button>' +
    '</div>'
};

async function mountModal() {
  const wrapper = mount(JuliaPrimaryModal, {
    global: { stubs: { JuliaModal: ModalStub } }
  });
  // onMounted flips the ref; let the resulting re-render settle.
  await nextTick();

  return wrapper;
}

describe('JuliaPrimaryModal', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.useFakeTimers();
    vi.setSystemTime(PRIMARY_DAY_STARTS_AT);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('opens the modal on mount when it has not been dismissed this session', async () => {
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('true');
  });

  it('keeps the modal closed when already dismissed this session', async () => {
    sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  it('never opens the modal once the primary is over', async () => {
    vi.setSystemTime(PRIMARY_MODAL_EXPIRES_AT);
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  // The countdown is generated on mount rather than baked into the prerendered
  // HTML, so each of these is what a visitor loading the page then would see.
  const countdownCases: [string, number, string][] = [
    [
      'days out',
      PRIMARY_DAY_STARTS_AT - 11 * DAY_MS,
      'Primary Election Day is in 11 days on August 11!'
    ],
    [
      'two days out',
      PRIMARY_DAY_STARTS_AT - 1.5 * DAY_MS,
      'Primary Election Day is in 2 days on August 11!'
    ],
    ['the day before', PRIMARY_DAY_STARTS_AT - 1, 'Primary Election Day is tomorrow, August 11!'],
    ['election day itself', PRIMARY_DAY_STARTS_AT, 'Primary Election Day is today, August 11!'],
    [
      'late on election day',
      PRIMARY_MODAL_EXPIRES_AT - 1,
      'Primary Election Day is today, August 11!'
    ]
  ];

  it.each(countdownCases)('reads correctly %s', async (_label, now, expected) => {
    vi.setSystemTime(now);
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').text()).toContain(expected);
  });

  it('records the dismissed flag and closes the modal on cancel', async () => {
    const wrapper = await mountModal();

    await wrapper.find('.modal-cancel').trigger('click');

    expect(sessionStorage.getItem(PRIMARY_MODAL_KEY)).toBe('true');
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });
});
