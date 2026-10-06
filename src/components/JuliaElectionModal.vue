<script setup lang="ts">
import { onMounted, ref } from 'vue';
import JuliaModal from './JuliaModal.vue';

defineOptions({
  name: 'JuliaElectionModal'
});

// Election reminder shown once per browser session. This component is mounted
// by App.vue, which outlives router navigation, so it never re-fires when
// moving between pages; the sessionStorage flag also keeps it dismissed across
// reloads within the session.
const ELECTION_MODAL_KEY = 'electionModalDismissed';

// General election day, as a Central calendar date.
const ELECTION_DAY = { year: 2026, month: 11, day: 3 };
const ELECTION_DAY_UTC = Date.UTC(ELECTION_DAY.year, ELECTION_DAY.month - 1, ELECTION_DAY.day);
// "November 3" — every date shown in the copy comes from ELECTION_DAY.
const ELECTION_DAY_LABEL = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  month: 'long',
  day: 'numeric'
}).format(ELECTION_DAY_UTC);

const DAY_MS = 24 * 60 * 60 * 1000;
const centralDateParts = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric'
});

const showElectionModal = ref(false);
const electionCountdown = ref('');
const isElectionDay = ref(false);

// Calendar days from today in Mankato to election day, so the count matches
// the calendar a voter there is looking at whatever the visitor's timezone.
// Counting dates rather than dividing elapsed time by 24h matters here: DST
// ends on November 1, two days before the election.
function daysUntilElection(now: number) {
  const parts = Object.fromEntries(
    centralDateParts.formatToParts(now).map(({ type, value }) => [type, Number(value)])
  );
  const today = Date.UTC(parts.year, parts.month - 1, parts.day);

  return Math.round((ELECTION_DAY_UTC - today) / DAY_MS);
}

function electionCountdownText(days: number) {
  if (days === 0) return `Election Day is today, ${ELECTION_DAY_LABEL}!`;
  if (days === 1) return `Election Day is tomorrow, ${ELECTION_DAY_LABEL}!`;

  // Inclusive count — today and election day both count, so October 31 reads
  // "4 days" rather than the 3 nights in between.
  return `Only ${days + 1} days until Election Day, ${ELECTION_DAY_LABEL}!`;
}

// Computed on mount, not during setup: vite-ssg runs setup at build time, and a
// count baked into the prerendered HTML would be wrong for every later visitor.
onMounted(() => {
  const days = daysUntilElection(Date.now());
  // Self-retires once election day is over in Mankato.
  if (days < 0) {
    return;
  }

  electionCountdown.value = electionCountdownText(days);
  isElectionDay.value = days === 0;

  if (sessionStorage.getItem(ELECTION_MODAL_KEY) !== 'true') {
    showElectionModal.value = true;
  }
});

function dismissElectionModal() {
  sessionStorage.setItem(ELECTION_MODAL_KEY, 'true');
}
</script>

<template>
  <JuliaModal
    v-model:open="showElectionModal"
    title="Important Reminder!"
    cancel-label="Close"
    @cancel="dismissElectionModal"
  >
    <p class="mb-4 rounded-lg bg-sprout/50 p-4 text-center font-accent text-xl">
      {{ electionCountdown }}
    </p>

    <p>
      Julia won 10 of Mankato’s 17 precincts in the primary. Now she needs your vote on
      {{ ELECTION_DAY_LABEL }} to become Mankato’s next mayor!
    </p>
    <!-- In-person early voting closes the day before the election. -->
    <p v-if="isElectionDay">Vote today at your local polling place!</p>
    <p v-else>
      You can
      <a
        href="https://www.sos.mn.gov/elections-voting/other-ways-to-vote/vote-early-in-person/"
        target="_blank"
        rel="noopener noreferrer"
        >vote early</a
      >
      at the Blue Earth County Historic Courthouse or at your local polling place on Election Day.
    </p>

    <p>
      Please help us spread the word and encourage others to vote for Julia on
      {{ ELECTION_DAY_LABEL }}!
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
