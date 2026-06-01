<script setup lang="ts">
import { computed, ref } from 'vue';
import sprout from '../assets/sprout.png';
import { submitContactForm } from '../lib/api';
import { trackVolunteerFormSubmit } from '../lib/analytics';

defineOptions({
    name: 'JuliaContactForm'
});

const firstName = ref('');
const lastName = ref('');
const email = ref('');
const phone = ref('');
const helpWays = ref<string[]>([]);
const message = ref('');
const firstNameError = ref('');
const emailError = ref('');
const submitError = ref('');
const isSubmitted = ref(false);
const isSubmitting = ref(false);

const fullName = computed(() => `${firstName.value.trim()} ${lastName.value.trim()}`.trim());

function validateFirstNameField(): boolean {
    if (!firstName.value.trim()) {
        firstNameError.value = 'Please enter your first name.';
        return false;
    }

    firstNameError.value = '';
    return true;
}

function isValidEmailFormat(value: string): boolean {
    const normalized = value.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(normalized);
}

function validateEmailField(): boolean {
    if (!isValidEmailFormat(email.value)) {
        emailError.value = 'Please enter a valid email address.';
        return false;
    }

    emailError.value = '';
    return true;
}

function handleSubmit(event: Event): void {
    event.preventDefault();

    if (isSubmitting.value) {
        return;
    }

    const isFirstNameValid = validateFirstNameField();
    const isEmailValid = validateEmailField();

    if (!isFirstNameValid || !isEmailValid) {
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
        message: message.value,
    };

    try {
        await submitContactForm(formData);
        trackVolunteerFormSubmit('success');
        isSubmitted.value = true;
    } catch (error) {
        trackVolunteerFormSubmit('error');
        submitError.value = error instanceof Error
            ? error.message
            : 'Unable to send your message right now. Please try again.';
    } finally {
        isSubmitting.value = false;
    }
}

const hasValidationError = computed(() => Boolean(firstNameError.value || emailError.value));
</script>

<template>
    <output v-if="isSubmitted" class="contact-form" aria-live="polite">
        <h3>Thanks so much for your support, {{ firstName.trim() || 'friend' }}!</h3>
        <p>
            Check your inbox for additional follow up. I look forward to working with you!
            <img class="success-sprout" :src="sprout" alt="" aria-hidden="true" />
        </p>
    </output>

    <form v-else class="contact-form" action="/api/send-email" method="POST" @submit="handleSubmit">
        <h3>Volunteer for the Campaign</h3>
        <p>* Fields marked with an asterisk are required.</p>

        <div class="name-fields">
            <div class="name-field">
                <label for="contact-first-name" class="sr-only">First Name *</label>
                <input id="contact-first-name" name="firstName" type="text" v-model="firstName" placeholder="First Name *"
                    @blur="validateFirstNameField" :class="{ 'input-error': firstNameError }" autocomplete="given-name" required />
                <p v-if="firstNameError" class="form-error-message" role="alert" aria-live="polite">{{ firstNameError }}</p>
            </div>

            <div class="name-field">
                <label for="contact-last-name" class="sr-only">Last Name</label>
                <input id="contact-last-name" name="lastName" type="text" v-model="lastName" placeholder="Last Name"
                    autocomplete="family-name" />
            </div>
        </div>

        <input type="hidden" name="name" :value="fullName" />

        <label for="contact-email" class="sr-only">Email *</label>
        <input id="contact-email" name="email" type="email" v-model="email" @blur="validateEmailField"
            :class="{ 'input-error': emailError }" placeholder="Email *" autocomplete="email" required />
        <p v-if="emailError" class="form-error-message" role="alert" aria-live="polite">{{ emailError }}</p>

        <label for="contact-phone" class="sr-only">Phone</label>
        <input id="contact-phone" name="phone" type="tel" v-model="phone" placeholder="Phone" autocomplete="tel" />

        <fieldset class="help-options">
            <legend>Ways you'd like to help</legend>
            <label class="help-option" for="help-canvassing">
                <input id="help-canvassing" name="helpWays[]" type="checkbox" value="Canvassing" v-model="helpWays" />
                Canvassing
            </label>
            <label class="help-option" for="help-events">
                <input id="help-events" name="helpWays[]" type="checkbox" value="Events" v-model="helpWays" />
                Host a Meet &amp; Greet
            </label>
            <label class="help-option" for="help-letter-to-editor">
                <input id="help-letter-to-editor" name="helpWays[]" type="checkbox" value="Letter to the editor"
                    v-model="helpWays" />
                Letter to the editor
            </label>
            <label class="help-option" for="help-fundraiser">
                <input id="help-fundraiser" name="helpWays[]" type="checkbox" value="Fundraiser" v-model="helpWays" />
                Host a fundraiser
            </label>
            <label class="help-option" for="help-campaign-team">
                <input id="help-campaign-team" name="helpWays[]" type="checkbox" value="Campaign team"
                    v-model="helpWays" />
                Join the campaign team
            </label>
            <label class="help-option" for="help-yard-signs">
                <input id="help-yard-signs" name="helpWays[]" type="checkbox" value="Yard signs" v-model="helpWays" />
                Put up a yard sign
            </label>
        </fieldset>

        <label for="contact-message" class="sr-only">Message</label>
        <textarea id="contact-message" name="message" v-model="message" placeholder="How would you like to help? Tell us about your other special skills or ideas!"
            rows="5"></textarea>

        <button v-if="!isSubmitting" type="submit" :disabled="hasValidationError">Send Message</button>
        <output v-else class="form-loading-message" aria-live="polite">Sending your message...</output>
        <p v-if="submitError" class="form-error-message" role="alert" aria-live="assertive">{{ submitError }}</p>
    </form>
</template>