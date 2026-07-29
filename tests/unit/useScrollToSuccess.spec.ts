import { flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useScrollToSuccess } from '../../src/composables/useScrollToSuccess';

function mountTarget() {
  const element = document.createElement('div');
  element.tabIndex = -1;
  document.body.appendChild(element);
  return element;
}

describe('useScrollToSuccess', () => {
  let scrollTo: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 0 });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('smooth-scrolls to the success message and focuses it', async () => {
    const element = mountTarget();
    const focus = vi.spyOn(element, 'focus');
    const isSubmitted = ref(false);

    useScrollToSuccess(ref<HTMLElement | null>(element), isSubmitted);

    isSubmitted.value = true;
    await flushPromises();

    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ behavior: 'smooth' }));
    // Without `preventScroll`, focusing an off-screen element scrolls it into
    // view instantly and cancels the smooth scroll started a line earlier.
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
  });

  it('does not scroll again while the form stays submitted', async () => {
    const element = mountTarget();
    const successRef = ref<HTMLElement | null>(element);
    const isSubmitted = ref(false);

    useScrollToSuccess(successRef, isSubmitted);

    isSubmitted.value = true;
    await flushPromises();
    successRef.value = mountTarget();
    await flushPromises();

    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('does nothing until the form is submitted', async () => {
    const element = mountTarget();
    useScrollToSuccess(ref<HTMLElement | null>(element), ref(false));

    await flushPromises();

    expect(scrollTo).not.toHaveBeenCalled();
  });
});
