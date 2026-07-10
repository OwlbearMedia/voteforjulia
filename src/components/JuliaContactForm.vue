<script setup lang="ts">
import { useTemplateRef } from 'vue';
import sprout from '../assets/sprout.png';
import IconSpinner from './icons/IconSpinner.vue';
import { useContactForm } from '../composables/useContactForm';
import { useScrollToSuccess } from '../composables/useScrollToSuccess';

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
const successMessageRef = useTemplateRef<HTMLElement>('successMessageRef');
useScrollToSuccess(successMessageRef, isSubmitted);
</script>

<template>
  <Transition name="contact-state" mode="out-in">
    <output
      v-if="isSubmitted"
      key="success"
      ref="successMessageRef"
      class="contact-form"
      aria-live="polite"
      tabindex="-1"
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
            :aria-invalid="!!firstNameError || undefined"
            :aria-describedby="firstNameError ? 'contact-first-name-error' : undefined"
            autocomplete="given-name"
            required
            @blur="validateFirstNameField"
          />
          <p
            v-if="firstNameError"
            id="contact-first-name-error"
            class="form-error-message"
            role="alert"
            aria-live="polite"
          >
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
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'contact-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="contact-last-name-error"
            class="form-error-message"
            role="alert"
            aria-live="polite"
          >
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
        :aria-invalid="!!emailError || undefined"
        :aria-describedby="emailError ? 'contact-email-error' : undefined"
        placeholder="Email *"
        autocomplete="email"
        required
        @blur="validateEmailField"
      />
      <p
        v-if="emailError"
        id="contact-email-error"
        class="form-error-message"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="contact-phone" class="sr-only">Phone</label>
      <input
        id="contact-phone"
        v-model="phone"
        name="phone"
        type="tel"
        placeholder="Phone"
        :aria-invalid="!!phoneError || undefined"
        :aria-describedby="phoneError ? 'contact-phone-error' : undefined"
        autocomplete="tel"
        @blur="validatePhoneField"
      />
      <p
        v-if="phoneError"
        id="contact-phone-error"
        class="form-error-message"
        role="alert"
        aria-live="polite"
      >
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
      </fieldset>

      <label for="contact-message" class="sr-only">Message</label>
      <textarea
        id="contact-message"
        v-model="message"
        name="message"
        placeholder="How would you like to help? Tell us about your other special skills or ideas!"
        :aria-invalid="!!messageError || undefined"
        :aria-describedby="messageError ? 'contact-message-error' : undefined"
        rows="5"
        @blur="validateMessageField"
      ></textarea>
      <p
        v-if="messageError"
        id="contact-message-error"
        class="form-error-message"
        role="alert"
        aria-live="polite"
      >
        {{ messageError }}
      </p>

      <button type="submit" :disabled="hasValidationError || isSubmitting">
        Send Message <IconSpinner v-if="isSubmitting" />
      </button>
      <p v-if="submitError" class="form-error-message" role="alert" aria-live="assertive">
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
