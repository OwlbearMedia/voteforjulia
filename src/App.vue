<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterView, useRoute } from 'vue-router';
import JuliaHeader from './components/JuliaHeader.vue';
import JuliaFooter from './components/JuliaFooter.vue';
import JuliaModal from './components/JuliaModal.vue';

const route = useRoute();

// Primary-election reminder shown once per browser session. App.vue outlives
// router navigation, so this never re-fires when moving between pages; the
// sessionStorage flag also keeps it dismissed across reloads within the session.
const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

// The reminder self-retires once the primary is over — after that it would be
// telling visitors to go vote in an election that already happened. Midnight
// CDT (UTC-5) at the end of election day, August 11 2026.
const PRIMARY_MODAL_EXPIRES_AT = Date.parse('2026-08-12T05:00:00Z');

const showPrimaryModal = ref(false);

onMounted(() => {
  if (Date.now() >= PRIMARY_MODAL_EXPIRES_AT) {
    return;
  }

  if (sessionStorage.getItem(PRIMARY_MODAL_KEY) !== 'true') {
    showPrimaryModal.value = true;
  }
});

function dismissPrimaryModal() {
  sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
}

const pageHeaderTitle = computed(() => {
  const routeTitles: Record<string, string> = {
    '/meet-julia': 'Get to Know Julia Hamann — Mankato Mayor Candidate',
    '/volunteer': 'Join Julia’s Team — Volunteer in Mankato',
    '/donate': 'Support Julia Hamann’s Campaign for Mankato Mayor',
    '/events': 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor',
    '/endorsements': 'Endorsements for Julia Hamann — Mankato Mayor',
    '/secret-recipe': 'Julia’s Famous Shrimp Salad Supreme Recipe',
    '/yard-signs': 'Get a Yard Sign — Julia Hamann for Mankato Mayor'
  };

  return routeTitles[route.path] ?? 'Elect Julia Hamann — A New Voice for Mankato';
});
</script>

<template>
  <JuliaHeader :title="pageHeaderTitle" />
  <main class="w-full max-w-[960px] flex-1 mx-auto px-8 text-forest max-md:p-5">
    <RouterView />
  </main>
  <JuliaFooter />

  <JuliaModal
    v-model:open="showPrimaryModal"
    title="Important Reminder!"
    cancel-label="Close"
    @cancel="dismissPrimaryModal"
  >
    <p class="font-accent bg-sprout/50 p-4 mb-4 text-center rounded-lg text-xl">
      Primary Election Day is August 11, 2026!
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
