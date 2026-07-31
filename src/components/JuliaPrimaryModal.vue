<script setup lang="ts">
import { onMounted, ref } from 'vue';
import JuliaModal from './JuliaModal.vue';

defineOptions({
  name: 'JuliaPrimaryModal'
});

// Primary-election reminder shown once per browser session. This component is
// mounted by App.vue, which outlives router navigation, so it never re-fires
// when moving between pages; the sessionStorage flag also keeps it dismissed
// across reloads within the session.
const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

// Midnight CDT (UTC-5) at the start of election day, August 11 2026.
const DAY_MS = 24 * 60 * 60 * 1000;
const PRIMARY_DAY_STARTS_AT = Date.parse('2026-08-11T05:00:00Z');

// The reminder self-retires once the primary is over — after that it would be
// telling visitors to go vote in an election that already happened.
const PRIMARY_MODAL_EXPIRES_AT = PRIMARY_DAY_STARTS_AT + DAY_MS;

const showPrimaryModal = ref(false);
const primaryCountdown = ref('');

// Nights left before the primary, counted from midnight CDT rather than the
// visitor's own timezone so the number matches the calendar a Mankato voter is
// looking at. Zero on election day itself.
function nightsUntilPrimary(now: number) {
  return Math.ceil((PRIMARY_DAY_STARTS_AT - now) / DAY_MS);
}

function primaryCountdownText(now: number) {
  const nights = nightsUntilPrimary(now);
  if (nights <= 0) return 'Primary Election Day is today, August 11!';
  if (nights === 1) return 'Primary Election Day is tomorrow, August 11!';

  // Inclusive count — today and election day both count, so July 31 reads
  // "12 days" rather than the 11 nights in between.
  return `Only ${nights + 1} days until Primary Election Day, August 11!`;
}

// Computed on mount, not during setup: vite-ssg runs setup at build time, and a
// count baked into the prerendered HTML would be wrong for every later visitor.
onMounted(() => {
  const now = Date.now();
  if (now >= PRIMARY_MODAL_EXPIRES_AT) {
    return;
  }

  primaryCountdown.value = primaryCountdownText(now);

  if (sessionStorage.getItem(PRIMARY_MODAL_KEY) !== 'true') {
    showPrimaryModal.value = true;
  }
});

function dismissPrimaryModal() {
  sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
}
</script>

<template>
  <JuliaModal
    v-model:open="showPrimaryModal"
    title="Important Reminder!"
    cancel-label="Close"
    @cancel="dismissPrimaryModal"
  >
    <p class="font-accent bg-sprout/50 p-4 mb-4 text-center rounded-lg text-xl">
      {{ primaryCountdown }}
    </p>

    <p>
      Julia needs your vote in the Primary to ensure her campaign continues on to the November
      election!
    </p>
    <p>
      You can
      <a
        href="https://www.sos.mn.gov/elections-voting/other-ways-to-vote/vote-early-in-person/"
        target="_blank"
        rel="noopener noreferrer"
        >vote early</a
      >
      at the Blue Earth County Historic Courthouse or at your local polling place on primary
      election day.
    </p>

    <p>
      Please help us spread the word and encourage others to vote for Julia in the Primary election!
    </p>

    <p class="mt-2">
      Check your voter registration:
      <a
        href="https://www.sos.mn.gov/elections-voting/register-to-vote/"
        target="_blank"
        rel="noopener noreferrer"
        >sos.mn.gov</a
      >
    </p>
    <p class="mt-2">
      Find your polling place:
      <a
        href="https://www.sos.mn.gov/elections-voting/election-day-voting"
        target="_blank"
        rel="noopener noreferrer"
        >sos.mn.gov</a
      >
    </p>
  </JuliaModal>
</template>
