<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import sprout from '../assets/sprout.png';
import IconSpinner from './icons/IconSpinner.vue';
import { useYardSignForm } from '../composables/useYardSignForm';

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
  successElement.focus();
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
      aria-live="polite"
      tabindex="-1"
    >
      <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
      <div class="contact-form-success">
        <p>
          Check your inbox for additional follow up. Your yard sign is on its way!
          <img class="success-sprout" :src="sprout" alt="" aria-hidden="true" />
        </p>
        If you plan to pay online you can <RouterLink to="/donate">make a donation</RouterLink> and
        write "yard sign" in the comment section.
      </div>
    </output>

    <form
      v-else
      key="form"
      class="contact-form"
      action="/api/yard-sign"
      method="POST"
      @submit="handleSubmit"
    >
      <h3>Get a Yard Sign</h3>
      <p>* Fields marked with an asterisk are required.</p>

      <div class="name-fields">
        <div class="name-field">
          <label for="yard-sign-first-name" class="sr-only">First Name *</label>
          <input
            id="yard-sign-first-name"
            v-model="firstName"
            name="firstName"
            type="text"
            placeholder="First Name *"
            :class="{ 'input-error': firstNameError }"
            :aria-invalid="!!firstNameError || undefined"
            :aria-describedby="firstNameError ? 'yard-sign-first-name-error' : undefined"
            autocomplete="given-name"
            required
            @blur="validateFirstNameField"
          />
          <p
            v-if="firstNameError"
            id="yard-sign-first-name-error"
            class="form-error-message"
            role="alert"
            aria-live="polite"
          >
            {{ firstNameError }}
          </p>
        </div>

        <div class="name-field">
          <label for="yard-sign-last-name" class="sr-only">Last Name</label>
          <input
            id="yard-sign-last-name"
            v-model="lastName"
            name="lastName"
            type="text"
            placeholder="Last Name"
            :aria-invalid="!!lastNameError || undefined"
            :aria-describedby="lastNameError ? 'yard-sign-last-name-error' : undefined"
            autocomplete="family-name"
            @blur="validateLastNameField"
          />
          <p
            v-if="lastNameError"
            id="yard-sign-last-name-error"
            class="form-error-message"
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
        :class="{ 'input-error': emailError }"
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
        class="form-error-message"
        role="alert"
        aria-live="polite"
      >
        {{ emailError }}
      </p>

      <label for="yard-sign-phone" class="sr-only">Phone</label>
      <input
        id="yard-sign-phone"
        v-model="phone"
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
        class="form-error-message"
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
        :class="{ 'input-error': addressError }"
        :aria-invalid="!!addressError || undefined"
        :aria-describedby="addressError ? 'yard-sign-address-error' : undefined"
        autocomplete="street-address"
        required
        @blur="validateAddressField"
      />
      <p
        v-if="addressError"
        id="yard-sign-address-error"
        class="form-error-message"
        role="alert"
        aria-live="polite"
      >
        {{ addressError }}
      </p>

      <fieldset class="help-options">
        <legend>Preferred payment</legend>
        <label class="help-option" for="yard-sign-payment-online">
          <input
            id="yard-sign-payment-online"
            v-model="preferredPayment"
            name="preferredPayment[]"
            type="checkbox"
            value="Online"
          />
          Online
        </label>
        <label class="help-option" for="yard-sign-payment-cash">
          <input
            id="yard-sign-payment-cash"
            v-model="preferredPayment"
            name="preferredPayment[]"
            type="checkbox"
            value="Cash"
          />
          Cash
        </label>
        <label class="help-option" for="yard-sign-payment-check">
          <input
            id="yard-sign-payment-check"
            v-model="preferredPayment"
            name="preferredPayment[]"
            type="checkbox"
            value="Check"
          />
          Check
        </label>
      </fieldset>

      <button type="submit" :disabled="hasValidationError || isSubmitting">
        Request a Yard Sign <IconSpinner v-if="isSubmitting" />
      </button>
      <p v-if="submitError" class="form-error-message" role="alert" aria-live="assertive">
        {{ submitError }}
      </p>
    </form>
  </Transition>
</template>
