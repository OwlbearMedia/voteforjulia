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
      class="contact-form mt-4 max-w-[640px] grid gap-2.5"
      aria-live="polite"
      tabindex="-1"
    >
      <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
      <p>
        Check your inbox for additional follow up. I look forward to working with you!
        <img
          class="success-sprout inline w-[1.25em] h-[1.25em] align-text-bottom"
          :src="sprout"
          alt=""
          aria-hidden="true"
        />
      </p>
    </output>

    <form
      v-else
      key="form"
      class="contact-form mt-4 max-w-[640px] grid gap-2.5"
      action="/api/send-email"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Volunteer for the Campaign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="flex gap-4">
        <div class="flex-[1_1_50%] min-w-0 grid gap-2.5">
          <label for="contact-first-name" class="sr-only">First Name *</label>
          <input
            id="contact-first-name"
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            class="w-full border border-mist rounded-md py-2.5 px-3 text-forest bg-white/96"
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
            class="mt-[-0.1rem] mb-1 text-error text-sm"
            role="alert"
            aria-live="polite"
          >
            {{ firstNameError }}
          </p>
        </div>

        <div class="flex-[1_1_50%] min-w-0 grid gap-2.5">
          <label for="contact-last-name" class="sr-only">Last Name</label>
          <input
            id="contact-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            class="w-full border border-mist rounded-md py-2.5 px-3 text-forest bg-white/96"
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'contact-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="contact-last-name-error"
            class="mt-[-0.1rem] mb-1 text-error text-sm"
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
        class="w-full border border-mist rounded-md py-2.5 px-3 text-forest bg-white/96"
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
        class="mt-[-0.1rem] mb-1 text-error text-sm"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="contact-phone" class="sr-only">Phone</label>
      <input
        id="contact-phone"
        v-model="phone"
        class="w-full border border-mist rounded-md py-2.5 px-3 text-forest bg-white/96"
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
        class="mt-[-0.1rem] mb-1 text-error text-sm"
        role="alert"
        aria-live="polite"
      >
        {{ phoneError }}
      </p>

      <fieldset class="m-0 pb-1 border-none rounded-md flex flex-wrap gap-2">
        <legend class="w-full p-0 mb-3 font-semibold text-forest">Ways you'd like to help</legend>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="help-canvassing">
          <input
            id="help-canvassing"
            v-model="helpWays"
            name="helpWays[]"
            class="w-auto m-0"
            type="checkbox"
            value="Canvassing"
          />
          Canvassing
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="help-events">
          <input
            id="help-events"
            v-model="helpWays"
            name="helpWays[]"
            class="w-auto m-0"
            type="checkbox"
            value="Events"
          />
          Host a Meet &amp; Greet
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="help-letter-to-editor">
          <input
            id="help-letter-to-editor"
            v-model="helpWays"
            name="helpWays[]"
            class="w-auto m-0"
            type="checkbox"
            value="Letter to the editor"
          />
          Letter to the editor
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="help-fundraiser">
          <input
            id="help-fundraiser"
            v-model="helpWays"
            name="helpWays[]"
            class="w-auto m-0"
            type="checkbox"
            value="Fundraiser"
          />
          Host a fundraiser
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="help-campaign-team">
          <input
            id="help-campaign-team"
            v-model="helpWays"
            name="helpWays[]"
            class="w-auto m-0"
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
        class="w-full border border-mist rounded-md py-2.5 px-3 text-forest bg-white/96 resize-y min-h-[130px]"
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
        class="mt-[-0.1rem] mb-1 text-error text-sm"
        role="alert"
        aria-live="polite"
      >
        {{ messageError }}
      </p>

      <button
        type="submit"
        class="w-fit max-md:w-full mt-1 border-0 rounded-pill pt-3 pb-2 px-6 bg-forest text-white text-sm leading-[1.6] font-action font-semibold tracking-[0.05em] text-center justify-self-start cursor-pointer hover:bg-forest/70 disabled:opacity-60 disabled:cursor-not-allowed"
        :disabled="hasValidationError || isSubmitting"
      >
        Send Message <IconSpinner v-if="isSubmitting" />
      </button>
      <p
        v-if="submitError"
        class="mt-[-0.1rem] mb-1 text-error text-sm"
        role="alert"
        aria-live="assertive"
      >
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
