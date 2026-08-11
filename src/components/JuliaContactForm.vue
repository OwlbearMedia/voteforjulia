<script setup lang="ts">
import { useTemplateRef } from 'vue';
import sprout from '../assets/sprout.png';
import JuliaButton from './JuliaButton.vue';
import IconSpinner from './icons/IconSpinner.vue';
import { API_BASE_URL } from '../lib/api';
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
  referralCode,
  submitError,
  isSubmitted,
  isSubmitting,
  fullName,
  handleSubmit
} = useContactForm();

// Where the browser posts this form when it submits it natively — i.e. when
// JavaScript is unavailable and `handleSubmit` never runs to preventDefault.
// Absolute, not `/api/send-email`: the API is a different host (ADR-0003) and
// the static document root proxies nothing, so a same-origin action 404s and
// the submission is lost.
const submitUrl = `${API_BASE_URL}/send-email`;

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
      class="contact-form mt-4 grid max-w-[640px] gap-2.5"
      aria-live="polite"
      tabindex="-1"
    >
      <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
      <p>
        Check your inbox for additional follow up. I look forward to working with you!
        <img
          class="success-sprout inline h-[1.25em] w-[1.25em] align-text-bottom"
          :src="sprout"
          alt=""
          aria-hidden="true"
        />
      </p>
    </output>

    <form
      v-else
      key="form"
      class="contact-form mt-4 grid max-w-[640px] gap-2.5"
      :action="submitUrl"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Volunteer for the Campaign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="flex gap-4">
        <div class="grid min-w-0 flex-1 basis-1/2 gap-2.5">
          <label for="contact-first-name" class="sr-only">First Name *</label>
          <input
            id="contact-first-name"
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
            :class="{ 'input-error border-error': firstNameError }"
            :aria-invalid="!!firstNameError || undefined"
            :aria-describedby="firstNameError ? 'contact-first-name-error' : undefined"
            autocomplete="given-name"
            required
            @blur="validateFirstNameField"
          />
          <p
            v-if="firstNameError"
            id="contact-first-name-error"
            class="mt-[-0.1rem] mb-1 text-sm text-error"
            role="alert"
            aria-live="polite"
          >
            {{ firstNameError }}
          </p>
        </div>

        <div class="grid min-w-0 flex-1 basis-1/2 gap-2.5">
          <label for="contact-last-name" class="sr-only">Last Name</label>
          <input
            id="contact-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'contact-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="contact-last-name-error"
            class="mt-[-0.1rem] mb-1 text-sm text-error"
            role="alert"
            aria-live="polite"
          >
            {{ lastNameError }}
          </p>
        </div>
      </div>

      <input type="hidden" name="name" :value="fullName" />

      <!--
        Spam honeypot (ADR-0016). `.honeypot-field` is `display: none`, never
        `.sr-only` — see src/style.css. The label is real so that a stylesheet
        failure degrades to a visible, explained field rather than an
        unexplained one that silently rejects the submission.
      -->
      <div class="honeypot-field">
        <label for="contact-referral-code">Referral code (leave this field empty)</label>
        <input
          id="contact-referral-code"
          v-model="referralCode"
          name="referralCode"
          type="text"
          tabindex="-1"
          autocomplete="off"
        />
      </div>

      <label for="contact-email" class="sr-only">Email *</label>
      <input
        id="contact-email"
        v-model="email"
        name="email"
        type="email"
        class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
        :class="{ 'input-error border-error': emailError }"
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
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="contact-phone" class="sr-only">Phone</label>
      <input
        id="contact-phone"
        v-model="phone"
        class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
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
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ phoneError }}
      </p>

      <fieldset class="m-0 flex flex-wrap gap-2 rounded-md border-none pb-1">
        <legend class="mb-3 w-full p-0 font-semibold text-forest">Ways you'd like to help</legend>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="help-canvassing">
          <input
            id="help-canvassing"
            v-model="helpWays"
            name="helpWays[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Canvassing"
          />
          Canvassing
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="help-events">
          <input
            id="help-events"
            v-model="helpWays"
            name="helpWays[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Events"
          />
          Host a Meet &amp; Greet
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="help-letter-to-editor">
          <input
            id="help-letter-to-editor"
            v-model="helpWays"
            name="helpWays[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Letter to the editor"
          />
          Letter to the editor
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="help-fundraiser">
          <input
            id="help-fundraiser"
            v-model="helpWays"
            name="helpWays[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Fundraiser"
          />
          Host a fundraiser
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="help-campaign-team">
          <input
            id="help-campaign-team"
            v-model="helpWays"
            name="helpWays[]"
            class="m-0 w-auto"
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
        class="min-h-[130px] w-full resize-y rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
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
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ messageError }}
      </p>

      <JuliaButton
        type="submit"
        class="mt-1 w-fit justify-self-start text-sm max-md:w-full"
        :disabled="isSubmitting"
      >
        Send Message <IconSpinner v-if="isSubmitting" />
      </JuliaButton>
      <p
        v-if="submitError"
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="assertive"
      >
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
