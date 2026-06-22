<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faSpinner } from '@fortawesome/free-solid-svg-icons';
import sprout from '../assets/sprout.png';
import { useContactForm } from '../composables/useContactForm';

defineOptions({
  name: 'JuliaContactForm'
});

const {
  firstName,
  firstNameError,
  validateFirstNameField,
  lastName,
  lastNameError,
  validateLastNameField,
  email,
  emailError,
  validateEmailField,
  phone,
  phoneError,
  validatePhoneField,
  message,
  messageError,
  validateMessageField,
  helpWays,
  submitError,
  isSubmitted,
  isSubmitting,
  fullName,
  hasValidationError,
  handleSubmit
} = useContactForm();

// View-only concern: scroll the success message into view once it renders.
const successMessageRef = ref<HTMLElement | null>(null);
const hasScrolledToSuccess = ref(false);

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
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            :class="{ 'input-error': firstNameError }"
            autocomplete="given-name"
            required
            @blur="validateFirstNameField"
          />
          <p v-if="firstNameError" class="form-error-message" role="alert" aria-live="polite">
            {{ firstNameError }}
          </p>
        </div>

        <div class="name-field">
          <label for="contact-last-name" class="sr-only">Last Name</label>
          <input
            id="contact-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            autocomplete="family-name"
            @blur="validateLastNameField"
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
        v-model="email"
        name="email"
        type="email"
        :class="{ 'input-error': emailError }"
        placeholder="Email *"
        autocomplete="email"
        required
        @blur="validateEmailField"
      />
      <p v-if="emailError" class="form-error-message" role="alert" aria-live="polite">
        {{ emailError }}
      </p>

      <label for="contact-phone" class="sr-only">Phone</label>
      <input
        id="contact-phone"
        v-model="phone"
        name="phone"
        type="tel"
        placeholder="Phone"
        autocomplete="tel"
        @blur="validatePhoneField"
      />
      <p v-if="phoneError" class="form-error-message" role="alert" aria-live="polite">
        {{ phoneError }}
      </p>

      <fieldset class="help-options">
        <legend>Ways you'd like to help</legend>
        <label class="help-option" for="help-canvassing">
          <input
            id="help-canvassing"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Canvassing"
          />
          Canvassing
        </label>
        <label class="help-option" for="help-events">
          <input
            id="help-events"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Events"
          />
          Host a Meet &amp; Greet
        </label>
        <label class="help-option" for="help-letter-to-editor">
          <input
            id="help-letter-to-editor"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Letter to the editor"
          />
          Letter to the editor
        </label>
        <label class="help-option" for="help-fundraiser">
          <input
            id="help-fundraiser"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Fundraiser"
          />
          Host a fundraiser
        </label>
        <label class="help-option" for="help-campaign-team">
          <input
            id="help-campaign-team"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Campaign team"
          />
          Join the campaign team
        </label>
        <label class="help-option" for="help-yard-signs">
          <input
            id="help-yard-signs"
            v-model="helpWays"
            name="helpWays[]"
            type="checkbox"
            value="Yard signs"
          />
          Put up a yard sign
        </label>
      </fieldset>

      <label for="contact-message" class="sr-only">Message</label>
      <textarea
        id="contact-message"
        v-model="message"
        name="message"
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
