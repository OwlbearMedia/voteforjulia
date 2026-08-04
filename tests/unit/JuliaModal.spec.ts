import { mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import JuliaModal from '../../src/components/JuliaModal.vue';

// The modal teleports to <body> and locks body scroll, so tests query the real
// document and attach to it (mirrors JuliaFooter.spec.ts's teleport handling).

let wrapper: VueWrapper | null = null;

function mountModal(props: Record<string, unknown> = {}, slot = '<p>Modal body</p>') {
  wrapper = mount(JuliaModal, {
    attachTo: document.body,
    props: { title: 'Action Needed', open: true, ...props },
    slots: { default: slot }
  });
  return wrapper;
}

function getDialog(): HTMLElement | null {
  return document.body.querySelector('[role="dialog"]');
}

function buttonByText(text: string): HTMLButtonElement | undefined {
  return Array.from(
    document.body.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')
  ).find((button) => button.textContent?.trim() === text);
}

function lastUpdateOpen(w: VueWrapper): boolean | undefined {
  const events = w.emitted('update:open') as boolean[][] | undefined;
  return events?.at(-1)?.[0];
}

beforeEach(() => {
  Object.defineProperty(window, 'scrollY', { configurable: true, value: 0 });
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  // Any test that left the body locked shouldn't leak styles into the next one.
  document.body.removeAttribute('style');
});

describe('JuliaModal', () => {
  it('renders nothing when closed', () => {
    mountModal({ open: false });
    expect(getDialog()).toBeNull();
  });

  it('renders the title, body slot, and dialog a11y attributes when open', () => {
    mountModal({ title: 'Action Needed' });

    const dialog = getDialog();
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
    expect(dialog?.textContent).toContain('Action Needed');
    expect(dialog?.textContent).toContain('Modal body');

    // aria-labelledby points at the rendered title heading.
    const labelledBy = dialog?.getAttribute('aria-labelledby');
    const heading = dialog?.querySelector('h2');
    expect(labelledBy).toBeTruthy();
    expect(heading?.id).toBe(labelledBy);

    // The level is asserted, not incidental: the only heading above a modal is
    // App.vue's visually-hidden h1, so anything below h2 skips a level and
    // fails axe's heading-order. Dropping back to h3 must fail here rather
    // than only showing up as a Lighthouse regression.
    expect(dialog?.querySelector('h3')).toBeNull();
  });

  it('hides the icon on the default variant and shows it on danger/warning', () => {
    mountModal({ variant: 'default' });
    expect(document.body.querySelector('[role="dialog"] .rounded-full')).toBeNull();
    wrapper?.unmount();

    mountModal({ variant: 'warning' });
    expect(
      document.body.querySelector('[role="dialog"] .rounded-full.text-warning')
    ).not.toBeNull();
    wrapper?.unmount();

    mountModal({ variant: 'danger' });
    expect(document.body.querySelector('[role="dialog"] .rounded-full.text-error')).not.toBeNull();
  });

  it('only renders the confirm/cancel buttons when their labels are set', () => {
    mountModal({ confirmLabel: '', cancelLabel: '' });
    expect(document.body.querySelectorAll('[role="dialog"] .rounded-pill')).toHaveLength(0);
    wrapper?.unmount();

    mountModal({ confirmLabel: 'Yes', cancelLabel: 'No' });
    expect(buttonByText('Yes')).toBeDefined();
    expect(buttonByText('No')).toBeDefined();
  });

  it('recolors the confirm button red only on the danger variant', () => {
    mountModal({ confirmLabel: 'Delete', variant: 'danger' });
    expect(buttonByText('Delete')?.classList.contains('bg-error')).toBe(true);
    wrapper?.unmount();

    mountModal({ confirmLabel: 'Save', variant: 'warning' });
    expect(buttonByText('Save')?.classList.contains('bg-leaf')).toBe(true);
  });

  it('emits confirm and closes when the confirm button is clicked', async () => {
    const w = mountModal({ confirmLabel: 'Confirm' });
    buttonByText('Confirm')?.click();
    await nextTick();

    expect(w.emitted('confirm')).toHaveLength(1);
    expect(lastUpdateOpen(w)).toBe(false);
  });

  it('emits cancel and closes when the cancel button is clicked', async () => {
    const w = mountModal({ cancelLabel: 'Dismiss' });
    buttonByText('Dismiss')?.click();
    await nextTick();

    expect(w.emitted('cancel')).toHaveLength(1);
    expect(lastUpdateOpen(w)).toBe(false);
  });

  it('emits cancel and closes when the X close button is clicked', async () => {
    const w = mountModal();
    (document.body.querySelector('[aria-label="Close"]') as HTMLElement).click();
    await nextTick();

    expect(w.emitted('cancel')).toHaveLength(1);
    expect(lastUpdateOpen(w)).toBe(false);
  });

  it('closes on the Escape key', async () => {
    const w = mountModal();
    getDialog()?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await nextTick();

    expect(w.emitted('cancel')).toHaveLength(1);
    expect(lastUpdateOpen(w)).toBe(false);
  });

  it('wraps focus from the last focusable element back to the first on Tab', () => {
    mountModal({ confirmLabel: 'OK', cancelLabel: 'Cancel' });
    const closeButton = document.body.querySelector('[aria-label="Close"]') as HTMLElement;
    const cancelButton = buttonByText('Cancel') as HTMLButtonElement;

    cancelButton.focus();
    getDialog()?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));

    expect(document.activeElement).toBe(closeButton);
  });

  // The trap must only intervene at the two edges. Anywhere in between, Tab has
  // to fall through to the browser's own focus order.
  it('leaves Tab alone when focus is not on the last focusable element', () => {
    mountModal({ confirmLabel: 'OK', cancelLabel: 'Cancel' });
    const closeButton = document.body.querySelector('[aria-label="Close"]') as HTMLElement;

    closeButton.focus();
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    getDialog()?.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(closeButton);
  });

  it('leaves Shift+Tab alone when focus is not on the first focusable element', () => {
    mountModal({ confirmLabel: 'OK', cancelLabel: 'Cancel' });
    const cancelButton = buttonByText('Cancel') as HTMLButtonElement;

    cancelButton.focus();
    const event = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey: true,
      bubbles: true,
      cancelable: true
    });
    getDialog()?.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(cancelButton);
  });

  it('ignores keys other than Escape and Tab', () => {
    const w = mountModal({ confirmLabel: 'OK' });
    const event = new KeyboardEvent('keydown', { key: 'a', bubbles: true, cancelable: true });
    getDialog()?.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(w.emitted('cancel')).toBeUndefined();
    expect(lastUpdateOpen(w)).toBeUndefined();
  });

  // Defensive guard: the header's close button means the panel always has a
  // focusable child today, but `last.focus()` would throw on an empty set, so
  // Tab has to no-op rather than crash if that ever stops being true.
  it('does not throw on Tab when the panel has no focusable children', () => {
    mountModal({ confirmLabel: 'OK', cancelLabel: 'Cancel' });
    const panel = getDialog() as HTMLElement;
    panel.querySelectorAll('button').forEach((button) => button.remove());
    panel.focus();

    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    expect(() => panel.dispatchEvent(event)).not.toThrow();
    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(panel);
  });

  it('moves focus to the confirm button when it opens', async () => {
    const w = mountModal({ open: false, confirmLabel: 'OK' });
    await w.setProps({ open: true });
    await nextTick();
    await nextTick();

    expect(document.activeElement).toBe(buttonByText('OK'));
  });

  // The confirm button is optional. Without this fallback, focus stays on
  // <body> and Escape/Tab never reach the panel's keydown handler, stranding
  // keyboard users behind the backdrop.
  it('moves focus to the panel when it opens without a confirm button', async () => {
    const w = mountModal({ open: false });
    await w.setProps({ open: true });
    await nextTick();
    await nextTick();

    expect(document.activeElement).toBe(getDialog());
  });

  it('closes on Escape when there is no confirm button', async () => {
    const w = mountModal({ open: false });
    await w.setProps({ open: true });
    await nextTick();
    await nextTick();

    document.activeElement?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    );
    await nextTick();

    expect(w.emitted('cancel')).toHaveLength(1);
    expect(lastUpdateOpen(w)).toBe(false);
  });

  it('wraps focus backwards from the panel to the last focusable element', async () => {
    const w = mountModal({ open: false, cancelLabel: 'Close' });
    await w.setProps({ open: true });
    await nextTick();
    await nextTick();

    getDialog()?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true })
    );

    expect(document.activeElement).toBe(buttonByText('Close'));
  });

  it('locks and restores body scroll around open/close', async () => {
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 150 });
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});

    const w = mountModal({ open: false });
    expect(document.body.style.position).toBe('');

    await w.setProps({ open: true });
    expect(document.body.style.position).toBe('fixed');
    expect(document.body.style.top).toBe('-150px');
    expect(document.body.style.overflow).toBe('hidden');

    await w.setProps({ open: false });
    expect(document.body.style.position).toBe('');
    expect(document.body.style.overflow).toBe('');
    expect(scrollTo).toHaveBeenCalledWith(0, 150);
  });

  it('unlocks body scroll if it unmounts while still open', async () => {
    const w = mountModal({ open: false });
    await w.setProps({ open: true });
    expect(document.body.style.position).toBe('fixed');

    w.unmount();
    wrapper = null;
    expect(document.body.style.position).toBe('');
  });
});
