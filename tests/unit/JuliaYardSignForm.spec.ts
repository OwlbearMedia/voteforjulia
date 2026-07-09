import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import JuliaYardSignForm from '../../src/components/JuliaYardSignForm.vue';
import { submitYardSignForm } from '../../src/lib/api';
import {
  trackYardSignFormSubmit,
  trackYardSignRequestBody,
  trackYardSignSubmissionError
} from '../../src/lib/analytics';

vi.mock('../../src/lib/api', () => ({
  submitYardSignForm: vi.fn()
}));

vi.mock('../../src/lib/analytics', () => ({
  trackYardSignFormSubmit: vi.fn(),
  trackYardSignRequestBody: vi.fn(),
  trackYardSignSubmissionError: vi.fn()
}));

describe('JuliaYardSignForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows validation errors and does not submit when required fields are invalid', async () => {
    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('Please enter your first name.');
    expect(wrapper.text()).toContain('Please enter a valid email address.');
    expect(wrapper.text()).toContain('Please enter your address.');
    expect(submitYardSignForm).not.toHaveBeenCalled();
  });

  it('blocks submission when address exceeds the backend limit', async () => {
    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-address').setValue('x'.repeat(201));

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('Address must be 200 characters or fewer.');
    expect(submitYardSignForm).not.toHaveBeenCalled();
  });

  it('submits a valid payload and tracks success', async () => {
    vi.mocked(submitYardSignForm).mockResolvedValueOnce();

    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-last-name').setValue('Hamann');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-phone').setValue('555-111-2222');
    await wrapper.find('#yard-sign-address').setValue('123 Main St, Mankato, MN 56001');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(submitYardSignForm).toHaveBeenCalledWith({
      firstName: 'Julia',
      lastName: 'Hamann',
      email: 'julia@example.com',
      phone: '555-111-2222',
      address: '123 Main St, Mankato, MN 56001',
      preferredPayment: ''
    });
    expect(trackYardSignRequestBody).toHaveBeenCalledWith({
      firstName: 'Julia',
      lastName: 'Hamann',
      email: 'julia@example.com',
      phone: '555-111-2222',
      address: '123 Main St, Mankato, MN 56001',
      preferredPayment: ''
    });
    expect(trackYardSignFormSubmit).toHaveBeenCalledWith('success');
    expect(wrapper.find('form').exists()).toBe(false);
    expect(wrapper.text()).toContain('Thanks so much for your support, Julia!');
  });

  it('shows dedicated success state content after successful submission', async () => {
    vi.mocked(submitYardSignForm).mockResolvedValueOnce();

    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-address').setValue('123 Main St');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('form').exists()).toBe(false);
    expect(wrapper.find('output.contact-form').exists()).toBe(true);
    expect(wrapper.text()).toContain('Thanks so much for your support, Julia!');
    expect(wrapper.find('.success-sprout').exists()).toBe(true);
  });

  it('shows API error message and tracks submission failure', async () => {
    vi.mocked(submitYardSignForm).mockRejectedValueOnce(new Error('Server unavailable'));

    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-address').setValue('123 Main St');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(trackYardSignSubmissionError).toHaveBeenCalledWith(expect.any(Error), {
      firstName: 'Julia',
      lastName: '',
      email: 'julia@example.com',
      phone: '',
      address: '123 Main St',
      preferredPayment: ''
    });
    expect(trackYardSignFormSubmit).toHaveBeenCalledWith('error');
    expect(wrapper.text()).toContain('Server unavailable');
  });

  // ─── Checkbox selection ─────────────────────────────────────────────────────

  describe('preferred payment checkboxes', () => {
    it('joins multiple selected checkboxes into a comma-separated string', async () => {
      vi.mocked(submitYardSignForm).mockResolvedValueOnce();
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').setValue('Julia');
      await wrapper.find('#yard-sign-email').setValue('julia@example.com');
      await wrapper.find('#yard-sign-address').setValue('123 Main St');
      await wrapper.find('#yard-sign-payment-online').setValue(true);
      await wrapper.find('#yard-sign-payment-check').setValue(true);
      await wrapper.find('form').trigger('submit');
      await flushPromises();
      expect(submitYardSignForm).toHaveBeenCalledWith(
        expect.objectContaining({ preferredPayment: 'Online, Check' })
      );
    });

    it('submits an empty string when no checkboxes are selected', async () => {
      vi.mocked(submitYardSignForm).mockResolvedValueOnce();
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').setValue('Julia');
      await wrapper.find('#yard-sign-email').setValue('julia@example.com');
      await wrapper.find('#yard-sign-address').setValue('123 Main St');
      await wrapper.find('form').trigger('submit');
      await flushPromises();
      expect(submitYardSignForm).toHaveBeenCalledWith(
        expect.objectContaining({ preferredPayment: '' })
      );
    });
  });

  // ─── Blur validation ─────────────────────────────────────────────────────────

  describe('blur validation', () => {
    it('shows first name error when first name field is blurred while empty', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').trigger('blur');
      expect(wrapper.text()).toContain('Please enter your first name.');
    });

    it('shows address error when address field is blurred while empty', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-address').trigger('blur');
      expect(wrapper.text()).toContain('Please enter your address.');
    });

    it('shows email error when email is invalid on blur', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-email').setValue('not-an-email');
      await wrapper.find('#yard-sign-email').trigger('blur');
      expect(wrapper.text()).toContain('Please enter a valid email address.');
    });

    it('shows phone error when phone is too long on blur', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-phone').setValue('1'.repeat(33));
      await wrapper.find('#yard-sign-phone').trigger('blur');
      expect(wrapper.text()).toContain('Phone must be 32 characters or fewer.');
    });
  });

  // ─── ARIA attributes ──────────────────────────────────────────────────────────

  describe('ARIA attributes', () => {
    it('sets aria-invalid on fields that fail validation on submit', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('form').trigger('submit');
      expect(wrapper.find('#yard-sign-first-name').attributes('aria-invalid')).toBe('true');
      expect(wrapper.find('#yard-sign-email').attributes('aria-invalid')).toBe('true');
      expect(wrapper.find('#yard-sign-address').attributes('aria-invalid')).toBe('true');
    });

    it('removes aria-invalid once a field error is resolved', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').trigger('blur');
      expect(wrapper.find('#yard-sign-first-name').attributes('aria-invalid')).toBe('true');
      await wrapper.find('#yard-sign-first-name').setValue('Julia');
      await wrapper.find('#yard-sign-first-name').trigger('blur');
      expect(wrapper.find('#yard-sign-first-name').attributes('aria-invalid')).toBeUndefined();
    });
  });

  // ─── Submit button state ──────────────────────────────────────────────────────

  describe('submit button disabled state', () => {
    it('disables the submit button while validation errors are present', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').trigger('blur');
      expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined();
    });

    it('re-enables the submit button once all errors are resolved', async () => {
      const wrapper = mount(JuliaYardSignForm);
      await wrapper.find('#yard-sign-first-name').setValue('Julia');
      await wrapper.find('#yard-sign-email').setValue('julia@example.com');
      await wrapper.find('#yard-sign-address').setValue('123 Main St');
      await wrapper.find('#yard-sign-first-name').trigger('blur');
      await wrapper.find('#yard-sign-email').trigger('blur');
      await wrapper.find('#yard-sign-address').trigger('blur');
      expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined();
    });
  });

  it('disables submit button and shows spinner while request is in flight', async () => {
    let resolveSubmission: () => void = () => {};
    const pendingSubmission = new Promise<void>((resolve) => {
      resolveSubmission = resolve;
    });

    vi.mocked(submitYardSignForm).mockReturnValueOnce(pendingSubmission);

    const wrapper = mount(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-address').setValue('123 Main St');

    await wrapper.find('form').trigger('submit');

    const submitButton = wrapper.find('button[type="submit"]');
    expect(submitButton.exists()).toBe(true);
    expect(submitButton.attributes('disabled')).toBeDefined();
    expect(wrapper.find('svg.icon-spin').exists()).toBe(true);

    resolveSubmission();
    await flushPromises();

    expect(wrapper.find('form').exists()).toBe(false);
  });
});
