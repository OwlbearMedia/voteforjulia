<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faSpinner } from '@fortawesome/free-solid-svg-icons';
import sprout from '../assets/sprout.png';
import { submitContactForm } from '../lib/api';
import {
  trackVolunteerFormSubmit,
  trackVolunteerRequestBody,
  trackVolunteerSubmissionError
} from '../lib/analytics';

defineOptions({
  name: 'JuliaContactForm'
});

const MAX_FIRST_NAME_LENGTH = 80;
const MAX_LAST_NAME_LENGTH = 80;
const MAX_EMAIL_LENGTH = 254;
const MAX_PHONE_LENGTH = 32;
const MAX_MESSAGE_LENGTH = 500;

const EMAIL_REGEX = /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$/i;

const firstName = ref('');
const lastName = ref('');
const email = ref('');
const phone = ref('');
const helpWays = ref<string[]>([]);
const message = ref('');
const firstNameError = ref('');
const lastNameError = ref('');
const emailError = ref('');
const phoneError = ref('');
const messageError = ref('');
const submitError = ref('');
const isSubmitted = ref(false);
const isSubmitting = ref(false);
const successMessageRef = ref<HTMLElement | null>(null);
const hasScrolledToSuccess = ref(false);

const fullName = computed(() => `${firstName.value.trim()} ${lastName.value.trim()}`.trim());

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

function validateFirstNameField(): boolean {
  const normalized = firstName.value.trim();

  if (!normalized) {
    firstNameError.value = 'Please enter your first name.';
    return false;
  }

  if (containsDisallowedControlChars(firstName.value, false)) {
    firstNameError.value = 'First name contains invalid characters.';
    return false;
  }

  if (normalized.length > MAX_FIRST_NAME_LENGTH) {
    firstNameError.value = `First name must be ${MAX_FIRST_NAME_LENGTH} characters or fewer.`;
    return false;
  }

  firstNameError.value = '';
  return true;
}

function validateLastNameField(): boolean {
  const normalized = lastName.value.trim();

  if (containsDisallowedControlChars(lastName.value, false)) {
    lastNameError.value = 'Last name contains invalid characters.';
    return false;
  }

  if (normalized.length > MAX_LAST_NAME_LENGTH) {
    lastNameError.value = `Last name must be ${MAX_LAST_NAME_LENGTH} characters or fewer.`;
    return false;
  }

  lastNameError.value = '';
  return true;
}

function isValidEmailFormat(value: string): boolean {
  const normalized = value.trim();
  return EMAIL_REGEX.test(normalized);
}

function validateEmailField(): boolean {
  const normalized = email.value.trim();

  if (containsDisallowedControlChars(email.value, false)) {
    emailError.value = 'Email contains invalid characters.';
    return false;
  }

  if (normalized.length > MAX_EMAIL_LENGTH) {
    emailError.value = `Email must be ${MAX_EMAIL_LENGTH} characters or fewer.`;
    return false;
  }

  if (!isValidEmailFormat(email.value)) {
    emailError.value = 'Please enter a valid email address.';
    return false;
  }

  emailError.value = '';
  return true;
}

function validatePhoneField(): boolean {
  const normalized = phone.value.trim();

  if (containsDisallowedControlChars(phone.value, false)) {
    phoneError.value = 'Phone contains invalid characters.';
    return false;
  }

  if (normalized.length > MAX_PHONE_LENGTH) {
    phoneError.value = `Phone must be ${MAX_PHONE_LENGTH} characters or fewer.`;
    return false;
  }

  phoneError.value = '';
  return true;
}

function validateMessageField(): boolean {
  if (containsDisallowedControlChars(message.value, true)) {
    messageError.value = 'Message contains invalid characters.';
    return false;
  }

  if (message.value.length > MAX_MESSAGE_LENGTH) {
    messageError.value = `Message must be ${MAX_MESSAGE_LENGTH} characters or fewer.`;
    return false;
  }

  messageError.value = '';
  return true;
}

function handleSubmit(event: Event): void {
  event.preventDefault();

  if (isSubmitting.value) {
    return;
  }

  const isFirstNameValid = validateFirstNameField();
  const isLastNameValid = validateLastNameField();
  const isEmailValid = validateEmailField();
  const isPhoneValid = validatePhoneField();
  const isMessageValid = validateMessageField();

  if (!isFirstNameValid || !isLastNameValid || !isEmailValid || !isPhoneValid || !isMessageValid) {
    submitError.value = '';
  } else {
    submitForm();
  }
}

async function submitForm(): Promise<void> {
  submitError.value = '';
  isSubmitting.value = true;

  const selectedHelpWays = [...helpWays.value];

  const formData = {
    firstName: firstName.value,
    lastName: lastName.value,
    email: email.value,
    phone: phone.value,
    helpWays: selectedHelpWays.join(', '),
    message: message.value
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

const hasValidationError = computed(() =>
  Boolean(
    firstNameError.value ||
    lastNameError.value ||
    emailError.value ||
    phoneError.value ||
    messageError.value
  )
);

async function scrollToSuccessMessage(): Promise<void> {
  await nextTick();

  const successElement = successMessageRef.value;
  if (!successElement || hasScrolledToSuccess.value) {
    return;
  }

  const headerElement = document.querySelector('header');
  const headerHeight =
    headerElement instanceof HTMLElement ? headerElement.getBoundingClientRect().height : 0;
  const targetTop = successElement.getBoundingClientRect().top + window.scrollY;
  const scrollTop = Math.max(targetTop - headerHeight - 8, 0);

  window.scrollTo({ top: scrollTop, behavior: 'smooth' });
  hasScrolledToSuccess.value = true;
}

watch(isSubmitted, (submitted) => {
  if (!submitted) {
    hasScrolledToSuccess.value = false;
    return;
  }

  void scrollToSuccessMessage();
});

watch(successMessageRef, (element) => {
  if (!element || !isSubmitted.value) {
    return;
  }

  void scrollToSuccessMessage();
});
</script>

<template>
  <Transition name="contact-state" mode="out-in">
    <output
      v-if="isSubmitted"
      key="success"
      ref="successMessageRef"
      class="contact-form"
      aria-live="polite"
    >
      <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
      <p>
        Check your inbox for additional follow up. I look forward to working with you!
        <img class="success-sprout" :src="sprout" alt="" aria-hidden="true" />
      </p>
    </output>

    <form
      v-else
      key="form"
      class="contact-form"
      action="/api/send-email"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Volunteer for the Campaign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="name-fields">
        <div class="name-field">
          <label for="contact-first-name" class="sr-only">First Name *</label>
          <input
            id="contact-first-name"
            name="firstName"
            type="text"
            v-model="firstName"
            placeholder="First Name *"
            @blur="validateFirstNameField"
            :class="{ 'input-error': firstNameError }"
            autocomplete="given-name"
            required
          />
          <p v-if="firstNameError" class="form-error-message" role="alert" aria-live="polite">
            {{ firstNameError }}
          </p>
        </div>

        <div class="name-field">
          <label for="contact-last-name" class="sr-only">Last Name</label>
          <input
            id="contact-last-name"
            name="lastName"
            type="text"
            v-model="lastName"
            placeholder="Last Name"
            @blur="validateLastNameField"
            autocomplete="family-name"
          />
          <p v-if="lastNameError" class="form-error-message" role="alert" aria-live="polite">
            {{ lastNameError }}
          </p>
        </div>
      </div>

      <input type="hidden" name="name" :value="fullName" />

      <label for="contact-email" class="sr-only">Email *</label>
      <input
        id="contact-email"
        name="email"
        type="email"
        v-model="email"
        @blur="validateEmailField"
        :class="{ 'input-error': emailError }"
        placeholder="Email *"
        autocomplete="email"
        required
      />
      <p v-if="emailError" class="form-error-message" role="alert" aria-live="polite">
        {{ emailError }}
      </p>

      <label for="contact-phone" class="sr-only">Phone</label>
      <input
        id="contact-phone"
        name="phone"
        type="tel"
        v-model="phone"
        placeholder="Phone"
        @blur="validatePhoneField"
        autocomplete="tel"
      />
      <p v-if="phoneError" class="form-error-message" role="alert" aria-live="polite">
        {{ phoneError }}
      </p>

      <fieldset class="help-options">
        <legend>Ways you'd like to help</legend>
        <label class="help-option" for="help-canvassing">
          <input
            id="help-canvassing"
            name="helpWays[]"
            type="checkbox"
            value="Canvassing"
            v-model="helpWays"
          />
          Canvassing
        </label>
        <label class="help-option" for="help-events">
          <input
            id="help-events"
            name="helpWays[]"
            type="checkbox"
            value="Events"
            v-model="helpWays"
          />
          Host a Meet &amp; Greet
        </label>
        <label class="help-option" for="help-letter-to-editor">
          <input
            id="help-letter-to-editor"
            name="helpWays[]"
            type="checkbox"
            value="Letter to the editor"
            v-model="helpWays"
          />
          Letter to the editor
        </label>
        <label class="help-option" for="help-fundraiser">
          <input
            id="help-fundraiser"
            name="helpWays[]"
            type="checkbox"
            value="Fundraiser"
            v-model="helpWays"
          />
          Host a fundraiser
        </label>
        <label class="help-option" for="help-campaign-team">
          <input
            id="help-campaign-team"
            name="helpWays[]"
            type="checkbox"
            value="Campaign team"
            v-model="helpWays"
          />
          Join the campaign team
        </label>
        <label class="help-option" for="help-yard-signs">
          <input
            id="help-yard-signs"
            name="helpWays[]"
            type="checkbox"
            value="Yard signs"
            v-model="helpWays"
          />
          Put up a yard sign
        </label>
      </fieldset>

      <label for="contact-message" class="sr-only">Message</label>
      <textarea
        id="contact-message"
        name="message"
        v-model="message"
        placeholder="How would you like to help? Tell us about your other special skills or ideas!"
        rows="5"
        @blur="validateMessageField"
      ></textarea>
      <p v-if="messageError" class="form-error-message" role="alert" aria-live="polite">
        {{ messageError }}
      </p>

      <button type="submit" :disabled="hasValidationError || isSubmitting">
        Send Message <FontAwesomeIcon v-if="isSubmitting" :icon="faSpinner" spin />
      </button>
      <p v-if="submitError" class="form-error-message" role="alert" aria-live="assertive">
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
