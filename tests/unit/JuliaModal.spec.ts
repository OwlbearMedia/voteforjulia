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

    // aria-labelledby points at the rendered <h3>.
    const labelledBy = dialog?.getAttribute('aria-labelledby');
    const heading = dialog?.querySelector('h3');
    expect(labelledBy).toBeTruthy();
    expect(heading?.id).toBe(labelledBy);
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
