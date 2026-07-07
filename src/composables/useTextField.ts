import { ref, type Ref } from 'vue';

export function containsDisallowedControlChars(value: string, allowNewlines: boolean): boolean {
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

export interface TextFieldOptions {
  /** Human-readable label used to build error messages, e.g. "First name". */
  label: string;
  /** Maximum allowed length of the raw field value. */
  max: number;
  /** When true, an empty value produces a "Please enter your …" error. */
  required?: boolean;
  /** When true, newlines are permitted (used by the freeform message field). */
  allowNewlines?: boolean;
  /** Optional format check (e.g. email), run after the basic checks pass. */
  format?: { test: (value: string) => boolean; message: string };
}

export interface TextField {
  value: Ref<string>;
  error: Ref<string>;
  validate: () => boolean;
}

/**
 * Builds a single reactive text field with its own value, error message, and
 * validator. Centralizing the rules here removes the near-identical
 * `validate*Field` functions each form composable would otherwise carry.
 */
export function useTextField(options: TextFieldOptions): TextField {
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

    if (value.value.length > options.max) {
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
