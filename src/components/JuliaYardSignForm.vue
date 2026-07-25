<script setup lang="ts">
import { useTemplateRef } from 'vue';
import { RouterLink } from 'vue-router';
import sprout from '../assets/sprout.png';
import IconSpinner from './icons/IconSpinner.vue';
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
  submitError,
  isSubmitted,
  isSubmitting,
  fullName,
  hasValidationError,
  handleSubmit
} = useYardSignForm();

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
      <div class="bg-sprout/50 rounded-lg py-4 px-6">
        <p>
          Check your inbox to coordinate sign delivery. We will be in touch soon!
          <img
            class="success-sprout inline w-[1.25em] h-[1.25em] align-text-bottom"
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
      class="contact-form mt-4 max-w-[640px] grid gap-[0.6rem]"
      action="/api/yard-sign"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Get a Yard Sign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="flex gap-4">
        <div class="flex-[1_1_50%] min-w-0 grid gap-[0.6rem]">
          <label for="yard-sign-first-name" class="sr-only">First Name *</label>
          <input
            id="yard-sign-first-name"
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            class="w-full border border-mist rounded-[0.4rem] py-[0.65rem] px-3 text-forest bg-white/96"
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
            class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
            role="alert"
            aria-live="polite"
          >
            {{ firstNameError }}
          </p>
        </div>

        <div class="flex-[1_1_50%] min-w-0 grid gap-[0.6rem]">
          <label for="yard-sign-last-name" class="sr-only">Last Name</label>
          <input
            id="yard-sign-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            class="w-full border border-mist rounded-[0.4rem] py-[0.65rem] px-3 text-forest bg-white/96"
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'yard-sign-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="yard-sign-last-name-error"
            class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
            role="alert"
            aria-live="polite"
          >
            {{ lastNameError }}
          </p>
        </div>
      </div>

      <input type="hidden" name="name" :value="fullName" />

      <label for="yard-sign-email" class="sr-only">Email *</label>
      <input
        id="yard-sign-email"
        v-model="email"
        name="email"
        type="email"
        class="w-full border border-mist rounded-[0.4rem] py-[0.65rem] px-3 text-forest bg-white/96"
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
        class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="yard-sign-phone" class="sr-only">Phone</label>
      <input
        id="yard-sign-phone"
        v-model="phone"
        class="w-full border border-mist rounded-[0.4rem] py-[0.65rem] px-3 text-forest bg-white/96"
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
        class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
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
        class="w-full border border-mist rounded-[0.4rem] py-[0.65rem] px-3 text-forest bg-white/96"
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
        class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
        role="alert"
        aria-live="polite"
      >
        {{ addressError }}
      </p>

      <fieldset class="m-0 pb-1 border-none rounded-[0.4rem] flex flex-wrap gap-[0.45rem]">
        <legend class="w-full p-0 mb-3 font-semibold text-forest">Preferred payment</legend>
        <label
          class="inline-flex items-center gap-2 font-normal mr-2"
          for="yard-sign-payment-online"
        >
          <input
            id="yard-sign-payment-online"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="w-auto m-0"
            type="checkbox"
            value="Online"
          />
          Online
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="yard-sign-payment-cash">
          <input
            id="yard-sign-payment-cash"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="w-auto m-0"
            type="checkbox"
            value="Cash"
          />
          Cash
        </label>
        <label
          class="inline-flex items-center gap-2 font-normal mr-2"
          for="yard-sign-payment-check"
        >
          <input
            id="yard-sign-payment-check"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="w-auto m-0"
            type="checkbox"
            value="Check"
          />
          Check
        </label>
        <label class="inline-flex items-center gap-2 font-normal mr-2" for="yard-sign-payment-done">
          <input
            id="yard-sign-payment-done"
            v-model="preferredPayment"
            name="preferredPayment[]"
            class="w-auto m-0"
            type="checkbox"
            value="Already Donated"
          />
          Already Donated
        </label>
      </fieldset>

      <button
        type="submit"
        class="w-fit max-desktop:w-full mt-1 border-0 rounded-pill pt-3 pb-2 px-6 bg-forest text-white text-[0.875rem] leading-[1.6] font-action font-semibold tracking-[0.05em] text-center justify-self-start cursor-pointer hover:bg-forest/70 disabled:opacity-60 disabled:cursor-not-allowed"
        :disabled="hasValidationError || isSubmitting"
      >
        Request a Yard Sign <IconSpinner v-if="isSubmitting" />
      </button>
      <p
        v-if="submitError"
        class="mt-[-0.1rem] mb-1 text-error text-[0.95rem]"
        role="alert"
        aria-live="assertive"
      >
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
