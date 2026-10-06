import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import JuliaElectionModal from '../../src/components/JuliaElectionModal.vue';

const ELECTION_MODAL_KEY = 'electionModalDismissed';

// Instants are written in Mankato local time with an explicit offset, so each
// reads as the wall clock a voter there would see. DST ends on November 1:
// CDT (-05:00) before it, CST (-06:00) from then through election day.
const at = (central: string) => Date.parse(central);
const ELECTION_DAY_STARTS_AT = at('2026-11-03T00:00:00-06:00');
const ELECTION_DAY_ENDS_AT = at('2026-11-04T00:00:00-06:00');

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
  const wrapper = mount(JuliaElectionModal, {
    global: { stubs: { JuliaModal: ModalStub } }
  });
  // onMounted flips the ref; let the resulting re-render settle.
  await nextTick();

  return wrapper;
}

describe('JuliaElectionModal', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.useFakeTimers();
    vi.setSystemTime(ELECTION_DAY_STARTS_AT);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('opens the modal on mount when it has not been dismissed this session', async () => {
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('true');
  });

  it('keeps the modal closed when already dismissed this session', async () => {
    sessionStorage.setItem(ELECTION_MODAL_KEY, 'true');
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  it('never opens the modal once election day is over in Mankato', async () => {
    vi.setSystemTime(ELECTION_DAY_ENDS_AT);
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });

  // The countdown is generated on mount rather than baked into the prerendered
  // HTML, so each of these is what a visitor loading the page then would see.
  // The day count is inclusive of both today and election day, so a visitor on
  // October 31 is told 4 days.
  const countdownCases: [string, number, string][] = [
    ['weeks out', at('2026-10-05T12:00:00-05:00'), 'Only 30 days until Election Day, November 3!'],
    // Just after midnight before DST ends: 3 days and 30 minutes of elapsed
    // time remain, so dividing by 24h instead of counting dates would say 5.
    [
      'just after midnight while still on daylight time',
      at('2026-10-31T00:30:00-05:00'),
      'Only 4 days until Election Day, November 3!'
    ],
    [
      'late on the day before daylight time ends',
      at('2026-10-31T23:59:00-05:00'),
      'Only 4 days until Election Day, November 3!'
    ],
    [
      'the day daylight time ends',
      at('2026-11-01T00:30:00-05:00'),
      'Only 3 days until Election Day, November 3!'
    ],
    [
      'the first minute of the day before',
      at('2026-11-02T00:00:00-06:00'),
      'Election Day is tomorrow, November 3!'
    ],
    ['the day before', ELECTION_DAY_STARTS_AT - 1, 'Election Day is tomorrow, November 3!'],
    ['election day itself', ELECTION_DAY_STARTS_AT, 'Election Day is today, November 3!'],
    ['late on election day', ELECTION_DAY_ENDS_AT - 1, 'Election Day is today, November 3!']
  ];

  it.each(countdownCases)('reads correctly %s', async (_label, now, expected) => {
    vi.setSystemTime(now);
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').text()).toContain(expected);
  });

  // The count is Mankato's calendar, not the visitor's. Each zone puts the
  // instant on a different date than Central, so these fail against code that
  // reads the visitor's local date on any host — including one in Central.
  const visitorTimezoneCases: [string, number, string][] = [
    // 4 a.m. November 2 in UTC; 6 p.m. November 2 in Kiritimati.
    [
      'Pacific/Kiritimati',
      at('2026-11-01T22:00:00-06:00'),
      'Only 3 days until Election Day, November 3!'
    ],
    // 8:30 p.m. November 2 in Honolulu.
    ['Pacific/Honolulu', at('2026-11-03T00:30:00-06:00'), 'Election Day is today, November 3!']
  ];

  it.each(visitorTimezoneCases)(
    'counts days in Central time for a visitor in %s',
    async (timezone, now, expected) => {
      const hostTimezone = process.env.TZ;
      process.env.TZ = timezone;
      try {
        vi.setSystemTime(now);
        const wrapper = await mountModal();
        expect(wrapper.find('.modal-stub').text()).toContain(expected);
      } finally {
        if (hostTimezone === undefined) delete process.env.TZ;
        else process.env.TZ = hostTimezone;
      }
    }
  );

  it('offers early voting until the day before the election', async () => {
    vi.setSystemTime(ELECTION_DAY_STARTS_AT - 1);
    const wrapper = await mountModal();
    expect(wrapper.find('.modal-stub').text()).toContain('vote early');
  });

  // In-person early voting closes the day before, so election day points only
  // at the polling place.
  it('does not offer early voting on election day', async () => {
    const wrapper = await mountModal();
    const text = wrapper.find('.modal-stub').text();
    expect(text).not.toContain('vote early');
    expect(text).toContain('Vote today at your local polling place!');
  });

  it('records the dismissed flag and closes the modal on cancel', async () => {
    const wrapper = await mountModal();

    await wrapper.find('.modal-cancel').trigger('click');

    expect(sessionStorage.getItem(ELECTION_MODAL_KEY)).toBe('true');
    expect(wrapper.find('.modal-stub').attributes('data-open')).toBe('false');
  });
});
