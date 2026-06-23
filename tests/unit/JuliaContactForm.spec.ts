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
