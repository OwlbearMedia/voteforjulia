<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import JuliaContactForm from '../components/JuliaContactForm.vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaVolunteer'
});

useHead(
  buildPageHead({
    path: '/volunteer',
    title: 'Volunteer | Julia Hamann for Mankato Mayor',
    description:
      'Volunteer for the Julia Hamann campaign to help build a more just, community-led Mankato.'
  })
);
</script>

<template>
  <section id="contact">
    <h2>Volunteer</h2>

    <div class="flex max-md:flex-col items-start gap-6 mb-4 *:flex-[1_1_50%] max-md:*:basis-auto">
      <div>
        <p>Join the campaign team to help with outreach, events, and voter engagement.</p>

        <JuliaContactForm />
      </div>
      <Image
        url-endpoint="https://ik.imagekit.io/voteforjulia"
        src="/julia.avif"
        alt="Julia Hamann for Mankato Mayor"
        class="w-full h-auto rounded-lg"
        sizes="(max-width: 767px) calc(100vw - 2.5rem), (max-width: 960px) calc((100vw - 5.5rem) / 2), 436px"
        :image-breakpoints="[240, 320, 420, 560, 727, 872, 1454]"
        :device-breakpoints="[]"
        width="1500"
        height="1500"
        crossorigin="anonymous"
        loading="lazy"
        decoding="async"
      />
    </div>
  </section>
</template>
