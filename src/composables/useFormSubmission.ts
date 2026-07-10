import { ref } from 'vue';
import type { TextField } from './useTextField';

export interface FormSubmissionOptions<T> {
  fields: TextField[];
  buildFormData: () => T;
  submit: (formData: T) => Promise<void>;
  trackRequest: (formData: T) => void;
  trackResult: (status: 'success' | 'error') => void;
  trackError: (error: unknown, formData: T) => void;
  fallbackErrorMessage: string;
}

/**
 * Drives the submit lifecycle shared by every form on the site: validate,
 * submit, track, and surface an error message. Centralizing this removes the
 * near-identical submitForm/handleSubmit pair each form composable would
 * otherwise carry.
 */
export function useFormSubmission<T>(options: FormSubmissionOptions<T>) {
  const submitError = ref('');
  const isSubmitted = ref(false);
  const isSubmitting = ref(false);

  async function submitForm(): Promise<void> {
    submitError.value = '';
    isSubmitting.value = true;

    const formData = options.buildFormData();

    try {
      options.trackRequest(formData);
      await options.submit(formData);
      options.trackResult('success');
      isSubmitted.value = true;
    } catch (error) {
      options.trackError(error, formData);
      options.trackResult('error');
      submitError.value = error instanceof Error ? error.message : options.fallbackErrorMessage;
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
    const allValid = options.fields.map((field) => field.validate()).every(Boolean);

    if (!allValid) {
      submitError.value = '';
      return;
    }

    void submitForm();
  }

  return { submitError, isSubmitted, isSubmitting, handleSubmit };
}
