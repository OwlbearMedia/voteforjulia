<script setup lang="ts">
import { Image } from '@imagekit/vue';
import { useHead } from '@unhead/vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaEndorsements'
});

// Placeholder endorsements — replace with real quotes, names, and titles.
const endorsements: { name: string; url: string }[] = [
  {
    name: 'Indivisible St. Peter/Greater Mankato',
    url: 'https://www.facebook.com/IndivisibleSPGM/posts/pfbid0MhUtKwfwrue3x8xXdrAhQdUDztbyohZRDAADa9k29Pha92fGxwjPxFSQ3htHAhual'
  }
];

useHead(
  buildPageHead({
    path: '/endorsements',
    title: 'Endorsements | Julia Hamann for Mankato Mayor',
    description:
      'See who’s endorsing Julia Hamann for Mayor of Mankato — community leaders, organizers, and neighbors standing behind her campaign.'
  })
);
</script>

<template>
  <section id="endorsements">
    <h2>Endorsements</h2>

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-xl">
      Julia is grateful to be endorsed by:
    </p>

    <ul class="grid grid-cols-3 max-md:grid-cols-1 gap-6 list-none p-0 my-8">
      <li v-for="(endorsement, index) in endorsements" :key="index">
        <figure class="flex flex-col">
          <a :href="endorsement.url" target="_blank" rel="noopener noreferrer" class="block">
            <Image
              url-endpoint="https://ik.imagekit.io/voteforjulia"
              src="/indivisible.png"
              alt="Julia Hamann for Mankato Mayor"
              class="w-full h-auto"
              sizes="(max-width: 767px) calc(100vw - 2.5rem), (max-width: 960px) calc((100vw - 7rem) / 3), 283px"
              :image-breakpoints="[240, 320, 440, 566, 728, 960, 1454]"
              :device-breakpoints="[]"
              width="960"
              height="960"
              crossorigin="anonymous"
              loading="lazy"
              decoding="async"
            />
          </a>
          <figcaption class="mt-4">
            <p class="font-accent text-[1.25rem] text-forest mb-0">{{ endorsement.name }}</p>
          </figcaption>
        </figure>
      </li>
    </ul>
  </section>
</template>
