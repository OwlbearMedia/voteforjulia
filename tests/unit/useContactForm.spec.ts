import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useContactForm } from '../../src/composables/useContactForm';
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

function fakeEvent(): Event {
  return { preventDefault: vi.fn() } as unknown as Event;
}

describe('useContactForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Field validation ───────────────────────────────────────────────────────

  describe('firstName field', () => {
    it('requires a non-empty value', () => {
      const { firstNameError, validateFirstNameField } = useContactForm();
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('Please enter your first name.');
    });

    it('treats whitespace-only input as empty', () => {
      const { firstName, firstNameError, validateFirstNameField } = useContactForm();
      firstName.value = '   ';
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('Please enter your first name.');
    });

    it('rejects values over 80 characters', () => {
      const { firstName, firstNameError, validateFirstNameField } = useContactForm();
      firstName.value = 'a'.repeat(81);
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('First name must be 80 characters or fewer.');
    });

    it('rejects control characters', () => {
      const { firstName, firstNameError, validateFirstNameField } = useContactForm();
      firstName.value = 'Julia\x01Whitney';
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('First name contains invalid characters.');
    });

    it('rejects embedded newlines', () => {
      const { firstName, firstNameError, validateFirstNameField } = useContactForm();
      firstName.value = 'Julia\nWhitney';
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('First name contains invalid characters.');
    });

    it('accepts a valid value and clears any prior error', () => {
      const { firstName, firstNameError, validateFirstNameField } = useContactForm();
      firstName.value = 'Julia';
      expect(validateFirstNameField()).toBe(true);
      expect(firstNameError.value).toBe('');
    });
  });

  describe('email field', () => {
    it('rejects an empty value with the format error', () => {
      const { emailError, validateEmailField } = useContactForm();
      expect(validateEmailField()).toBe(false);
      expect(emailError.value).toBe('Please enter a valid email address.');
    });

    it('rejects a malformed address', () => {
      const { email, emailError, validateEmailField } = useContactForm();
      email.value = 'not-an-email';
      expect(validateEmailField()).toBe(false);
      expect(emailError.value).toBe('Please enter a valid email address.');
    });

    it('rejects values over 254 characters', () => {
      const { email, emailError, validateEmailField } = useContactForm();
      email.value = `${'a'.repeat(243)}@example.com`; // 243 + 12 = 255 chars
      expect(validateEmailField()).toBe(false);
      expect(emailError.value).toBe('Email must be 254 characters or fewer.');
    });

    it('accepts a valid email address', () => {
      const { email, emailError, validateEmailField } = useContactForm();
      email.value = 'julia@example.com';
      expect(validateEmailField()).toBe(true);
      expect(emailError.value).toBe('');
    });
  });

  describe('message field', () => {
    it('rejects values over 500 characters', () => {
      const { message, messageError, validateMessageField } = useContactForm();
      message.value = 'x'.repeat(501);
      expect(validateMessageField()).toBe(false);
      expect(messageError.value).toBe('Message must be 500 characters or fewer.');
    });

    it('rejects whitespace-padded values over 500 raw characters', () => {
      const { message, messageError, validateMessageField } = useContactForm();
      message.value = `${' '.repeat(5)}${'x'.repeat(500)}${' '.repeat(5)}`;
      expect(validateMessageField()).toBe(false);
      expect(messageError.value).toBe('Message must be 500 characters or fewer.');
    });

    it('permits newlines', () => {
      const { message, messageError, validateMessageField } = useContactForm();
      message.value = 'line one\nline two\r\nline three';
      expect(validateMessageField()).toBe(true);
      expect(messageError.value).toBe('');
    });

    it('still rejects other control characters', () => {
      const { message, messageError, validateMessageField } = useContactForm();
      message.value = 'hello\x07world';
      expect(validateMessageField()).toBe(false);
      expect(messageError.value).toBe('Message contains invalid characters.');
    });
  });

  describe('optional fields (lastName, phone)', () => {
    it('accepts an empty last name', () => {
      const { lastNameError, validateLastNameField } = useContactForm();
      expect(validateLastNameField()).toBe(true);
      expect(lastNameError.value).toBe('');
    });

    it('rejects a last name over 80 characters', () => {
      const { lastName, lastNameError, validateLastNameField } = useContactForm();
      lastName.value = 'a'.repeat(81);
      expect(validateLastNameField()).toBe(false);
      expect(lastNameError.value).toBe('Last name must be 80 characters or fewer.');
    });

    it('rejects a phone number over 32 characters', () => {
      const { phone, phoneError, validatePhoneField } = useContactForm();
      phone.value = '1'.repeat(33);
      expect(validatePhoneField()).toBe(false);
      expect(phoneError.value).toBe('Phone must be 32 characters or fewer.');
    });
  });

  // ─── Computed properties ────────────────────────────────────────────────────

  describe('fullName', () => {
    it('trims and joins first and last name', () => {
      const { firstName, lastName, fullName } = useContactForm();
      firstName.value = 'Julia ';
      lastName.value = ' Hamann';
      expect(fullName.value).toBe('Julia Hamann');
    });

    it('returns only first name when last name is absent', () => {
      const { firstName, fullName } = useContactForm();
      firstName.value = 'Julia';
      expect(fullName.value).toBe('Julia');
    });
  });

  describe('hasValidationError', () => {
    it('is false initially', () => {
      const { hasValidationError } = useContactForm();
      expect(hasValidationError.value).toBe(false);
    });

    it('is true when any field has an error', () => {
      const { firstNameError, hasValidationError } = useContactForm();
      firstNameError.value = 'Please enter your first name.';
      expect(hasValidationError.value).toBe(true);
    });
  });

  // ─── handleSubmit ───────────────────────────────────────────────────────────

  describe('handleSubmit', () => {
    it('always calls event.preventDefault()', () => {
      const { handleSubmit } = useContactForm();
      const event = fakeEvent();
      handleSubmit(event);
      expect(event.preventDefault).toHaveBeenCalledOnce();
    });

    it('surfaces all field errors simultaneously (no short-circuit)', () => {
      const { firstNameError, emailError, handleSubmit } = useContactForm();
      handleSubmit(fakeEvent());
      // firstName is required; email fails format — both must be set in one pass
      expect(firstNameError.value).toBeTruthy();
      expect(emailError.value).toBeTruthy();
    });

    it('does not call the API when validation fails', () => {
      const { handleSubmit } = useContactForm();
      handleSubmit(fakeEvent());
      expect(submitContactForm).not.toHaveBeenCalled();
    });

    it('clears a stale submitError when validation fails', () => {
      const { submitError, handleSubmit } = useContactForm();
      submitError.value = 'Previous server error';
      handleSubmit(fakeEvent());
      expect(submitError.value).toBe('');
    });

    it('ignores a second submit while one is already in-flight', () => {
      const { firstName, email, isSubmitting, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      isSubmitting.value = true;
      handleSubmit(fakeEvent());
      expect(submitContactForm).not.toHaveBeenCalled();
    });

    it('calls the API with the correct payload', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const { firstName, lastName, email, phone, helpWays, message, handleSubmit } =
        useContactForm();
      firstName.value = 'Julia';
      lastName.value = 'Hamann';
      email.value = 'julia@example.com';
      phone.value = '555-111-2222';
      helpWays.value = ['Canvassing', 'Phone banking'];
      message.value = 'Happy to help!';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitContactForm).toHaveBeenCalledWith({
        firstName: 'Julia',
        lastName: 'Hamann',
        email: 'julia@example.com',
        phone: '555-111-2222',
        helpWays: 'Canvassing, Phone banking',
        message: 'Happy to help!'
      });
    });

    it('tracks the request body before sending', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const { firstName, email, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(trackVolunteerRequestBody).toHaveBeenCalledOnce();
      expect(trackVolunteerRequestBody).toHaveBeenCalledWith(
        expect.objectContaining({ firstName: 'Julia', email: 'julia@example.com' })
      );
    });

    it('sets isSubmitted and tracks success on a resolved API call', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const { firstName, email, isSubmitted, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(isSubmitted.value).toBe(true);
      expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('success');
    });

    it('sets submitError and tracks failure on a rejected API call', async () => {
      vi.mocked(submitContactForm).mockRejectedValueOnce(new Error('Server unavailable'));
      const { firstName, email, submitError, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitError.value).toBe('Server unavailable');
      expect(trackVolunteerSubmissionError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({ firstName: 'Julia' })
      );
      expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('error');
    });

    it('uses a generic message for non-Error rejections', async () => {
      vi.mocked(submitContactForm).mockRejectedValueOnce('timeout');
      const { firstName, email, submitError, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitError.value).toBe('Unable to send your message right now. Please try again.');
    });

    it('clears isSubmitting after a successful submission', async () => {
      vi.mocked(submitContactForm).mockResolvedValueOnce();
      const { firstName, email, isSubmitting, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      expect(isSubmitting.value).toBe(true);
      await flushPromises();
      expect(isSubmitting.value).toBe(false);
    });

    it('clears isSubmitting after a failed submission', async () => {
      vi.mocked(submitContactForm).mockRejectedValueOnce(new Error('fail'));
      const { firstName, email, isSubmitting, handleSubmit } = useContactForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';

      handleSubmit(fakeEvent());
      expect(isSubmitting.value).toBe(true);
      await flushPromises();
      expect(isSubmitting.value).toBe(false);
    });
  });
});
