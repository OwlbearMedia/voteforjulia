<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import JuliaHeader from './components/JuliaHeader.vue';
import JuliaFooter from './components/JuliaFooter.vue';
import JuliaModal from './components/JuliaModal.vue';

const route = useRoute();
const router = useRouter();

// Primary-election reminder shown once per browser session. App.vue outlives
// router navigation, so this never re-fires when moving between pages; the
// sessionStorage flag also keeps it dismissed across reloads within the session.
const PRIMARY_MODAL_KEY = 'primaryModalDismissed';
const showPrimaryModal = ref(false);

onMounted(() => {
  if (sessionStorage.getItem(PRIMARY_MODAL_KEY) !== 'true') {
    showPrimaryModal.value = true;
  }
});

function dismissPrimaryModal() {
  sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
}

function goToEvents() {
  dismissPrimaryModal();
  router.push('/events');
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
    variant="warning"
    title="Action Needed!"
    cancel-label="Close"
    @confirm="goToEvents"
    @cancel="dismissPrimaryModal"
  >
    <p class="font-accent bg-sprout/50 p-4 mb-4 text-center rounded-lg text-xl">
      Primary Election Day is August 11, 2026!
    </p>

    <p>
      Make sure you’re registered to vote and know where to go on primary election day. It really
      helps if you are spreading the word about the primary as well. Tell everyone you know (who is
      planning on voting for Julia)!
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
    <p class="mt-2">
      <a
        href="https://sites.google.com/indivisiblespgm.org/indivisiblespgm/elections/2026-mankato-mayor-primary"
        target="_blank"
        rel="noopener noreferrer"
        >Indivisible SPGM Mayor Primary Voter Guide</a
      >
    </p>
  </JuliaModal>
</template>
