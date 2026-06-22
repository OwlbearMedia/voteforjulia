import { computed, ref, type Ref } from 'vue';
import { submitContactForm } from '../lib/api';
import {
  trackVolunteerFormSubmit,
  trackVolunteerRequestBody,
  trackVolunteerSubmissionError
} from '../lib/analytics';

// Limits mirror the backend's accepted maximums so the client rejects
// over-long input before a request is ever made.
const FIELD_LIMITS = {
  firstName: 80,
  lastName: 80,
  email: 254,
  phone: 32,
  message: 500
} as const;

const EMAIL_REGEX = /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$/i;

function containsDisallowedControlChars(value: string, allowNewlines: boolean): boolean {
  for (const character of value) {
    if (character === '\n' || character === '\r') {
      if (allowNewlines) {
        continue;
      }

      return true;
    }

    const codePoint = character.codePointAt(0) ?? 0;
    if (codePoint < 32 || codePoint === 127) {
      return true;
    }
  }

  return false;
}

interface TextFieldOptions {
  /** Human-readable label used to build error messages, e.g. "First name". */
  label: string;
  /** Maximum allowed length after trimming. */
  max: number;
  /** When true, an empty value produces a "Please enter your …" error. */
  required?: boolean;
  /** When true, newlines are permitted (used by the freeform message field). */
  allowNewlines?: boolean;
  /** Optional format check (e.g. email), run after the basic checks pass. */
  format?: { test: (value: string) => boolean; message: string };
}

interface TextField {
  value: Ref<string>;
  error: Ref<string>;
  validate: () => boolean;
}

/**
 * Builds a single reactive text field with its own value, error message, and
 * validator. Centralising the rules here removes the six near-identical
 * `validate*Field` functions the component used to carry.
 */
function useTextField(options: TextFieldOptions): TextField {
  const value = ref('');
  const error = ref('');

  function validate(): boolean {
    const normalized = value.value.trim();

    if (options.required && !normalized) {
      error.value = `Please enter your ${options.label.toLowerCase()}.`;
      return false;
    }

    if (containsDisallowedControlChars(value.value, options.allowNewlines ?? false)) {
      error.value = `${options.label} contains invalid characters.`;
      return false;
    }

    if (normalized.length > options.max) {
      error.value = `${options.label} must be ${options.max} characters or fewer.`;
      return false;
    }

    if (options.format && !options.format.test(value.value)) {
      error.value = options.format.message;
      return false;
    }

    error.value = '';
    return true;
  }

  return { value, error, validate };
}

export function useContactForm() {
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
  const messageField = useTextField({
    label: 'Message',
    max: FIELD_LIMITS.message,
    allowNewlines: true
  });

  const fields = [firstNameField, lastNameField, emailField, phoneField, messageField];

  const helpWays = ref<string[]>([]);
  const submitError = ref('');
  const isSubmitted = ref(false);
  const isSubmitting = ref(false);

  const fullName = computed(() =>
    `${firstNameField.value.value.trim()} ${lastNameField.value.value.trim()}`.trim()
  );

  const hasValidationError = computed(() => fields.some((field) => field.error.value));

  async function submitForm(): Promise<void> {
    submitError.value = '';
    isSubmitting.value = true;

    const formData = {
      firstName: firstNameField.value.value,
      lastName: lastNameField.value.value,
      email: emailField.value.value,
      phone: phoneField.value.value,
      helpWays: [...helpWays.value].join(', '),
      message: messageField.value.value
    };

    try {
      trackVolunteerRequestBody(formData);
      await submitContactForm(formData);
      trackVolunteerFormSubmit('success');
      isSubmitted.value = true;
    } catch (error) {
      trackVolunteerSubmissionError(error, formData);
      trackVolunteerFormSubmit('error');
      submitError.value =
        error instanceof Error
          ? error.message
          : 'Unable to send your message right now. Please try again.';
    } finally {
      isSubmitting.value = false;
    }
  }

  function handleSubmit(event: Event): void {
    event.preventDefault();

    if (isSubmitting.value) {
      return;
    }

    // Validate every field (no short-circuit) so all errors surface at once.
    const allValid = fields.map((field) => field.validate()).every(Boolean);

    if (!allValid) {
      submitError.value = '';
      return;
    }

    void submitForm();
  }

  return {
    // Field models — names kept identical to the original component so the
    // template requires no changes.
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
    message: messageField.value,
    messageError: messageField.error,
    validateMessageField: messageField.validate,
    // Form-level state.
    helpWays,
    submitError,
    isSubmitted,
    isSubmitting,
    fullName,
    hasValidationError,
    handleSubmit
  };
}
