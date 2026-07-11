import { computed, ref } from 'vue';
import { submitYardSignForm } from '../lib/api';
import { EMAIL_REGEX, useTextField } from './useTextField';
import { useFormSubmission } from './useFormSubmission';
import {
  trackYardSignFormSubmit,
  trackYardSignRequestBody,
  trackYardSignSubmissionError
} from '../lib/analytics';

// Limits mirror the backend's accepted maximums so the client rejects
// over-long input before a request is ever made.
const FIELD_LIMITS = {
  firstName: 80,
  lastName: 80,
  email: 254,
  phone: 32,
  address: 200
} as const;

export function useYardSignForm() {
  const firstNameField = useTextField({
    label: 'First name',
    max: FIELD_LIMITS.firstName,
    required: true
  });
  const lastNameField = useTextField({ label: 'Last name', max: FIELD_LIMITS.lastName });
  const emailField = useTextField({
    label: 'Email',
    max: FIELD_LIMITS.email,
    // Not flagged `required`: an empty value falls through to the format check,
    // preserving the original "Please enter a valid email address." message.
    format: {
      test: (candidate) => EMAIL_REGEX.test(candidate.trim()),
      message: 'Please enter a valid email address.'
    }
  });
  const phoneField = useTextField({ label: 'Phone', max: FIELD_LIMITS.phone });
  const addressField = useTextField({
    label: 'Address',
    max: FIELD_LIMITS.address,
    required: true
  });

  const fields = [firstNameField, lastNameField, emailField, phoneField, addressField];

  const preferredPayment = ref<string[]>([]);

  const fullName = computed(() =>
    `${firstNameField.value.value.trim()} ${lastNameField.value.value.trim()}`.trim()
  );

  const hasValidationError = computed(() => fields.some((field) => field.error.value));

  const { submitError, isSubmitted, isSubmitting, handleSubmit } = useFormSubmission({
    fields,
    buildFormData: () => ({
      firstName: firstNameField.value.value,
      lastName: lastNameField.value.value,
      email: emailField.value.value,
      phone: phoneField.value.value,
      address: addressField.value.value,
      preferredPayment: [...preferredPayment.value].join(', ')
    }),
    submit: submitYardSignForm,
    trackRequest: trackYardSignRequestBody,
    trackResult: trackYardSignFormSubmit,
    trackError: trackYardSignSubmissionError,
    fallbackErrorMessage: 'Unable to send your request right now. Please try again.'
  });

  return {
    firstName: firstNameField.value,
    firstNameError: firstNameField.error,
    validateFirstNameField: firstNameField.validate,
    lastName: lastNameField.value,
    lastNameError: lastNameField.error,
    validateLastNameField: lastNameField.validate,
    email: emailField.value,
    emailError: emailField.error,
    validateEmailField: emailField.validate,
    phone: phoneField.value,
    phoneError: phoneField.error,
    validatePhoneField: phoneField.validate,
    address: addressField.value,
    addressError: addressField.error,
    validateAddressField: addressField.validate,
    preferredPayment,
    submitError,
    isSubmitted,
    isSubmitting,
    fullName,
    hasValidationError,
    handleSubmit
  };
}
