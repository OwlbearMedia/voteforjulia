import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import JuliaContactForm from '../../src/components/JuliaContactForm.vue';
import { submitContactForm } from '../../src/lib/api';
import {
  trackVolunteerFormSubmit,
  trackVolunteerRequestBody,
  trackVolunteerSubmissionError
} from '../../src/lib/analytics';

vi.mock('../../src/lib/api', () => ({
  submitContactForm: vi.fn()
}));

vi.mock('../../src/lib/analytics', () => ({
  trackVolunteerFormSubmit: vi.fn(),
  trackVolunteerRequestBody: vi.fn(),
  trackVolunteerSubmissionError: vi.fn()
}));

describe('JuliaContactForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows validation errors and does not submit when required fields are invalid', async () => {
    const wrapper = mount(JuliaContactForm);

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('Please enter your first name.');
    expect(wrapper.text()).toContain('Please enter a valid email address.');
    expect(submitContactForm).not.toHaveBeenCalled();
  });

  it('blocks submission when the message exceeds the backend limit', async () => {
    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');
    await wrapper.find('#contact-message').setValue('x'.repeat(501));

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('Message must be 500 characters or fewer.');
    expect(submitContactForm).not.toHaveBeenCalled();
  });

  it('blocks submission when first name exceeds the backend limit', async () => {
    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('x'.repeat(81));
    await wrapper.find('#contact-email').setValue('julia@example.com');

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('First name must be 80 characters or fewer.');
    expect(submitContactForm).not.toHaveBeenCalled();
  });

  it('submits a valid payload and tracks success', async () => {
    vi.mocked(submitContactForm).mockResolvedValueOnce();

    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-last-name').setValue('Hamann');
    await wrapper.find('#contact-email').setValue('julia@example.com');
    await wrapper.find('#contact-phone').setValue('555-111-2222');
    await wrapper.find('#help-canvassing').setValue(true);
    await wrapper.find('#contact-message').setValue('Happy to help on weekends');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(submitContactForm).toHaveBeenCalledWith({
      firstName: 'Julia',
      lastName: 'Hamann',
      email: 'julia@example.com',
      phone: '555-111-2222',
      helpWays: 'Canvassing',
      message: 'Happy to help on weekends'
    });
    expect(trackVolunteerRequestBody).toHaveBeenCalledWith({
      firstName: 'Julia',
      lastName: 'Hamann',
      email: 'julia@example.com',
      phone: '555-111-2222',
      helpWays: 'Canvassing',
      message: 'Happy to help on weekends'
    });
    expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('success');
    expect(wrapper.find('form').exists()).toBe(false);
    expect(wrapper.text()).toContain('Thanks so much for your support, Julia!');
  });

  it('shows dedicated success state content after successful submission', async () => {
    vi.mocked(submitContactForm).mockResolvedValueOnce();

    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('form').exists()).toBe(false);
    expect(wrapper.find('output.contact-form').exists()).toBe(true);
    expect(wrapper.text()).toContain('Thanks so much for your support, Julia!');
    expect(wrapper.text()).toContain(
      'Check your inbox for additional follow up. I look forward to working with you!'
    );
    expect(wrapper.find('.success-sprout').exists()).toBe(true);
  });

  it('shows API error message and tracks submission failure', async () => {
    vi.mocked(submitContactForm).mockRejectedValueOnce(new Error('Server unavailable'));

    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(trackVolunteerSubmissionError).toHaveBeenCalledWith(expect.any(Error), {
      firstName: 'Julia',
      lastName: '',
      email: 'julia@example.com',
      phone: '',
      helpWays: '',
      message: ''
    });
    expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('error');
    expect(wrapper.text()).toContain('Server unavailable');
  });

  // ─── Blur validation ─────────────────────────────────────────────────────────

  describe('blur validation', () => {
    it('shows first name error when first name field is blurred while empty', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.text()).toContain('Please enter your first name.');
    });

    it('clears first name error when field is corrected and re-blurred', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.text()).toContain('Please enter your first name.');
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.text()).not.toContain('Please enter your first name.');
    });

    it('shows last name error when last name is too long on blur', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-last-name').setValue('a'.repeat(81));
      await wrapper.find('#contact-last-name').trigger('blur');
      expect(wrapper.text()).toContain('Last name must be 80 characters or fewer.');
    });

    it('shows email error when email is invalid on blur', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-email').setValue('not-an-email');
      await wrapper.find('#contact-email').trigger('blur');
      expect(wrapper.text()).toContain('Please enter a valid email address.');
    });

    it('shows phone error when phone is too long on blur', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-phone').setValue('1'.repeat(33));
      await wrapper.find('#contact-phone').trigger('blur');
      expect(wrapper.text()).toContain('Phone must be 32 characters or fewer.');
    });

    it('shows message error when message is too long on blur', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-message').setValue('x'.repeat(501));
      await wrapper.find('#contact-message').trigger('blur');
      expect(wrapper.text()).toContain('Message must be 500 characters or fewer.');
    });
  });

  // ─── ARIA attributes ──────────────────────────────────────────────────────────

  describe('ARIA attributes', () => {
    it('sets aria-invalid on fields that fail validation on submit', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('form').trigger('submit');
      expect(wrapper.find('#contact-first-name').attributes('aria-invalid')).toBe('true');
      expect(wrapper.find('#contact-email').attributes('aria-invalid')).toBe('true');
    });

    it('removes aria-invalid once a field error is resolved', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('#contact-first-name').attributes('aria-invalid')).toBe('true');
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('#contact-first-name').attributes('aria-invalid')).toBeUndefined();
    });

    it('sets aria-describedby pointing to the error element when an error is present', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('#contact-first-name').attributes('aria-describedby')).toBe(
        'contact-first-name-error'
      );
      expect(wrapper.find('#contact-first-name-error').exists()).toBe(true);
    });

    it('removes aria-describedby once the error is resolved', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('#contact-first-name').attributes('aria-describedby')).toBeUndefined();
      expect(wrapper.find('#contact-first-name-error').exists()).toBe(false);
    });
  });

  // ─── Submit button state ──────────────────────────────────────────────────────

  describe('submit button disabled state', () => {
    it('disables the submit button while validation errors are present', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined();
    });

    it('re-enables the submit button once all errors are resolved', async () => {
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').trigger('blur');
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-first-name').trigger('blur');
      expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined();
    });
  });

  // ─── Checkbox selection ───────────────────────────────────────────────────────

  describe('help way checkboxes', () => {
    it('joins multiple selected checkboxes into a comma-separated string', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-email').setValue('julia@example.com');
      await wrapper.find('#help-canvassing').setValue(true);
      await wrapper.find('#help-events').setValue(true);
      await wrapper.find('#help-yard-signs').setValue(true);
      await wrapper.find('form').trigger('submit');
      await flushPromises();
      expect(submitContactForm).toHaveBeenCalledWith(
        expect.objectContaining({ helpWays: 'Canvassing, Events, Yard signs' })
      );
    });

    it('submits an empty string when no checkboxes are selected', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const wrapper = mount(JuliaContactForm);
      await wrapper.find('#contact-first-name').setValue('Julia');
      await wrapper.find('#contact-email').setValue('julia@example.com');
      await wrapper.find('form').trigger('submit');
      await flushPromises();
      expect(submitContactForm).toHaveBeenCalledWith(
        expect.objectContaining({ helpWays: '' })
      );
    });
  });

  it('disables submit button and shows spinner while request is in flight', async () => {
    let resolveSubmission: () => void = () => {};
    const pendingSubmission = new Promise<void>((resolve) => {
      resolveSubmission = resolve;
    });

    vi.mocked(submitContactForm).mockReturnValueOnce(pendingSubmission);

    const wrapper = mount(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');

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
