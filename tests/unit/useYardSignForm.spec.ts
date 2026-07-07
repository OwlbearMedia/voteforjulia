import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useYardSignForm } from '../../src/composables/useYardSignForm';
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

function fakeEvent(): Event {
  return { preventDefault: vi.fn() } as unknown as Event;
}

describe('useYardSignForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Field validation ───────────────────────────────────────────────────────

  describe('firstName field', () => {
    it('requires a non-empty value', () => {
      const { firstNameError, validateFirstNameField } = useYardSignForm();
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('Please enter your first name.');
    });

    it('rejects values over 80 characters', () => {
      const { firstName, firstNameError, validateFirstNameField } = useYardSignForm();
      firstName.value = 'a'.repeat(81);
      expect(validateFirstNameField()).toBe(false);
      expect(firstNameError.value).toBe('First name must be 80 characters or fewer.');
    });

    it('accepts a valid value and clears any prior error', () => {
      const { firstName, firstNameError, validateFirstNameField } = useYardSignForm();
      firstName.value = 'Julia';
      expect(validateFirstNameField()).toBe(true);
      expect(firstNameError.value).toBe('');
    });
  });

  describe('email field', () => {
    it('rejects an empty value with the format error', () => {
      const { emailError, validateEmailField } = useYardSignForm();
      expect(validateEmailField()).toBe(false);
      expect(emailError.value).toBe('Please enter a valid email address.');
    });

    it('rejects a malformed address', () => {
      const { email, emailError, validateEmailField } = useYardSignForm();
      email.value = 'not-an-email';
      expect(validateEmailField()).toBe(false);
      expect(emailError.value).toBe('Please enter a valid email address.');
    });

    it('accepts a valid email address', () => {
      const { email, emailError, validateEmailField } = useYardSignForm();
      email.value = 'julia@example.com';
      expect(validateEmailField()).toBe(true);
      expect(emailError.value).toBe('');
    });
  });

  describe('address field', () => {
    it('requires a non-empty value', () => {
      const { addressError, validateAddressField } = useYardSignForm();
      expect(validateAddressField()).toBe(false);
      expect(addressError.value).toBe('Please enter your address.');
    });

    it('rejects values over 200 characters', () => {
      const { address, addressError, validateAddressField } = useYardSignForm();
      address.value = 'a'.repeat(201);
      expect(validateAddressField()).toBe(false);
      expect(addressError.value).toBe('Address must be 200 characters or fewer.');
    });

    it('accepts a valid value and clears any prior error', () => {
      const { address, addressError, validateAddressField } = useYardSignForm();
      address.value = '123 Main St, Mankato, MN 56001';
      expect(validateAddressField()).toBe(true);
      expect(addressError.value).toBe('');
    });
  });

  describe('optional fields (lastName, phone)', () => {
    it('accepts an empty last name', () => {
      const { lastNameError, validateLastNameField } = useYardSignForm();
      expect(validateLastNameField()).toBe(true);
      expect(lastNameError.value).toBe('');
    });

    it('rejects a phone number over 32 characters', () => {
      const { phone, phoneError, validatePhoneField } = useYardSignForm();
      phone.value = '1'.repeat(33);
      expect(validatePhoneField()).toBe(false);
      expect(phoneError.value).toBe('Phone must be 32 characters or fewer.');
    });
  });

  // ─── Computed properties ────────────────────────────────────────────────────

  describe('fullName', () => {
    it('trims and joins first and last name', () => {
      const { firstName, lastName, fullName } = useYardSignForm();
      firstName.value = 'Julia ';
      lastName.value = ' Hamann';
      expect(fullName.value).toBe('Julia Hamann');
    });
  });

  describe('hasValidationError', () => {
    it('is false initially', () => {
      const { hasValidationError } = useYardSignForm();
      expect(hasValidationError.value).toBe(false);
    });

    it('is true when any field has an error', () => {
      const { firstNameError, hasValidationError } = useYardSignForm();
      firstNameError.value = 'Please enter your first name.';
      expect(hasValidationError.value).toBe(true);
    });
  });

  // ─── handleSubmit ───────────────────────────────────────────────────────────

  describe('handleSubmit', () => {
    it('always calls event.preventDefault()', () => {
      const { handleSubmit } = useYardSignForm();
      const event = fakeEvent();
      handleSubmit(event);
      expect(event.preventDefault).toHaveBeenCalledOnce();
    });

    it('surfaces all field errors simultaneously (no short-circuit)', () => {
      const { firstNameError, emailError, addressError, handleSubmit } = useYardSignForm();
      handleSubmit(fakeEvent());
      expect(firstNameError.value).toBeTruthy();
      expect(emailError.value).toBeTruthy();
      expect(addressError.value).toBeTruthy();
    });

    it('does not call the API when validation fails', () => {
      const { handleSubmit } = useYardSignForm();
      handleSubmit(fakeEvent());
      expect(submitYardSignForm).not.toHaveBeenCalled();
    });

    it('ignores a second submit while one is already in-flight', () => {
      const { firstName, email, address, isSubmitting, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      address.value = '123 Main St';
      isSubmitting.value = true;
      handleSubmit(fakeEvent());
      expect(submitYardSignForm).not.toHaveBeenCalled();
    });

    it('calls the API with the correct payload', async () => {
      vi.mocked(submitYardSignForm).mockResolvedValueOnce();
      const { firstName, lastName, email, phone, address, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      lastName.value = 'Hamann';
      email.value = 'julia@example.com';
      phone.value = '555-111-2222';
      address.value = '123 Main St, Mankato, MN 56001';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitYardSignForm).toHaveBeenCalledWith({
        firstName: 'Julia',
        lastName: 'Hamann',
        email: 'julia@example.com',
        phone: '555-111-2222',
        address: '123 Main St, Mankato, MN 56001'
      });
    });

    it('sets isSubmitted and tracks success on a resolved API call', async () => {
      vi.mocked(submitYardSignForm).mockResolvedValueOnce();
      const { firstName, email, address, isSubmitted, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      address.value = '123 Main St';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(isSubmitted.value).toBe(true);
      expect(trackYardSignFormSubmit).toHaveBeenCalledWith('success');
    });

    it('sets submitError and tracks failure on a rejected API call', async () => {
      vi.mocked(submitYardSignForm).mockRejectedValueOnce(new Error('Server unavailable'));
      const { firstName, email, address, submitError, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      address.value = '123 Main St';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitError.value).toBe('Server unavailable');
      expect(trackYardSignSubmissionError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({ firstName: 'Julia' })
      );
      expect(trackYardSignFormSubmit).toHaveBeenCalledWith('error');
    });

    it('uses a generic message for non-Error rejections', async () => {
      vi.mocked(submitYardSignForm).mockRejectedValueOnce('timeout');
      const { firstName, email, address, submitError, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      address.value = '123 Main St';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(submitError.value).toBe('Unable to send your request right now. Please try again.');
    });

    it('tracks the request body before sending', async () => {
      vi.mocked(submitYardSignForm).mockResolvedValueOnce();
      const { firstName, email, address, handleSubmit } = useYardSignForm();
      firstName.value = 'Julia';
      email.value = 'julia@example.com';
      address.value = '123 Main St';

      handleSubmit(fakeEvent());
      await flushPromises();

      expect(trackYardSignRequestBody).toHaveBeenCalledOnce();
      expect(trackYardSignRequestBody).toHaveBeenCalledWith(
        expect.objectContaining({ firstName: 'Julia', email: 'julia@example.com' })
      );
    });
  });
});
