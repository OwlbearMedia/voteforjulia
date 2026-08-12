<script setup lang="ts">
import { useTemplateRef } from 'vue';
import { RouterLink } from 'vue-router';
import sprout from '../assets/sprout.png';
import JuliaButton from './JuliaButton.vue';
import IconSpinner from './icons/IconSpinner.vue';
import { API_BASE_URL } from '../lib/api';
import { useYardSignForm } from '../composables/useYardSignForm';
import { useScrollToSuccess } from '../composables/useScrollToSuccess';

defineOptions({
  name: 'JuliaYardSignForm'
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
  address,
  addressError,
  validateAddressField,
  preferredPayment,
  referralCode,
  submitError,
  isSubmitted,
  isSubmitting,
  fullName,
  handleSubmit
} = useYardSignForm();

// Where the browser posts this form when it submits it natively — i.e. when
// JavaScript is unavailable and `handleSubmit` never runs to preventDefault.
// Absolute, not `/api/yard-sign`: the API is a different host (ADR-0003) and
// the static document root proxies nothing, so a same-origin action 404s and
// the submission is lost.
const submitUrl = `${API_BASE_URL}/yard-sign`;

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
      aria-live="polite"
      tabindex="-1"
    >
      <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
      <div class="rounded-lg bg-sprout/50 px-6 py-4">
        <p>
          Check your inbox to coordinate sign delivery. We will be in touch soon!
          <img
            class="success-sprout inline h-[1.25em] w-[1.25em] align-text-bottom"
            :src="sprout"
            alt=""
            aria-hidden="true"
          />
        </p>
        If you plan to pay online you can
        <RouterLink to="/donate" class="text-white/90">make a donation</RouterLink> and write "yard
        sign" in the comment section.
      </div>
    </output>

    <form
      v-else
      key="form"
      class="contact-form mt-4 grid max-w-[640px] gap-2.5"
      :action="submitUrl"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Get a Yard Sign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="flex gap-4">
        <div class="grid min-w-0 flex-1 basis-1/2 gap-2.5">
          <label for="yard-sign-first-name" class="sr-only">First Name *</label>
          <input
            id="yard-sign-first-name"
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
            :class="{ 'input-error border-error': firstNameError }"
            :aria-invalid="!!firstNameError || undefined"
            :aria-describedby="firstNameError ? 'yard-sign-first-name-error' : undefined"
            autocomplete="given-name"
            required
            @blur="validateFirstNameField"
          />
          <p
            v-if="firstNameError"
            id="yard-sign-first-name-error"
            class="mt-[-0.1rem] mb-1 text-sm text-error"
            role="alert"
            aria-live="polite"
          >
            {{ firstNameError }}
          </p>
        </div>

        <div class="grid min-w-0 flex-1 basis-1/2 gap-2.5">
          <label for="yard-sign-last-name" class="sr-only">Last Name</label>
          <input
            id="yard-sign-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'yard-sign-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="yard-sign-last-name-error"
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
        Spam honeypot (ADR-0016) — see JuliaContactForm.vue for why this is
        `display: none` via `.honeypot-field` and never `.sr-only`.
      -->
      <div class="honeypot-field">
        <label for="yard-sign-referral-code">Referral code (leave this field empty)</label>
        <input
          id="yard-sign-referral-code"
          v-model="referralCode"
          name="referralCode"
          type="text"
          tabindex="-1"
          autocomplete="off"
        />
      </div>

      <label for="yard-sign-email" class="sr-only">Email *</label>
      <input
        id="yard-sign-email"
        v-model="email"
        name="email"
        type="email"
        class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
        :class="{ 'input-error border-error': emailError }"
        :aria-invalid="!!emailError || undefined"
        :aria-describedby="emailError ? 'yard-sign-email-error' : undefined"
        placeholder="Email *"
        autocomplete="email"
        required
        @blur="validateEmailField"
      />
      <p
        v-if="emailError"
        id="yard-sign-email-error"
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="yard-sign-phone" class="sr-only">Phone</label>
      <input
        id="yard-sign-phone"
        v-model="phone"
        class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
        name="phone"
        type="tel"
        placeholder="Phone"
        :aria-invalid="!!phoneError || undefined"
        :aria-describedby="phoneError ? 'yard-sign-phone-error' : undefined"
        autocomplete="tel"
        @blur="validatePhoneField"
      />
      <p
        v-if="phoneError"
        id="yard-sign-phone-error"
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ phoneError }}
      </p>

      <label for="yard-sign-address" class="sr-only">Address *</label>
      <input
        id="yard-sign-address"
        v-model="address"
        name="address"
        type="text"
        placeholder="Address *"
        class="w-full rounded-md border border-mist bg-white/96 px-3 py-2.5 text-forest"
        :class="{ 'input-error border-error': addressError }"
        :aria-invalid="!!addressError || undefined"
        :aria-describedby="addressError ? 'yard-sign-address-error' : undefined"
        autocomplete="street-address"
        required
        @blur="validateAddressField"
      />
      <p
        v-if="addressError"
        id="yard-sign-address-error"
        class="mt-[-0.1rem] mb-1 text-sm text-error"
        role="alert"
        aria-live="polite"
      >
        {{ addressError }}
      </p>

      <fieldset class="m-0 flex flex-wrap gap-2 rounded-md border-none pb-1">
        <legend class="mb-3 w-full p-0 font-semibold text-forest">Preferred payment</legend>
        <label
          class="mr-2 inline-flex items-center gap-2 font-normal"
          for="yard-sign-payment-online"
        >
          <input
            id="yard-sign-payment-online"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Online"
          />
          Online
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="yard-sign-payment-cash">
          <input
            id="yard-sign-payment-cash"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Cash"
          />
          Cash
        </label>
        <label
          class="mr-2 inline-flex items-center gap-2 font-normal"
          for="yard-sign-payment-check"
        >
          <input
            id="yard-sign-payment-check"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Check"
          />
          Check
        </label>
        <label class="mr-2 inline-flex items-center gap-2 font-normal" for="yard-sign-payment-done">
          <input
            id="yard-sign-payment-done"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="m-0 w-auto"
            type="checkbox"
            value="Already Donated"
          />
          Already Donated
        </label>
      </fieldset>

      <JuliaButton
        type="submit"
        class="mt-1 w-fit justify-self-start text-sm max-md:w-full"
        :disabled="isSubmitting"
      >
        Request a Yard Sign <IconSpinner v-if="isSubmitting" />
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
