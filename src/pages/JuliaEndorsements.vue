<script setup lang="ts">
import { Image } from '@imagekit/vue';
import { useHead } from '@unhead/vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaEndorsements'
});

interface Endorsement {
  name: string;
  logo: string;
  url: string;
  body: string[];
  links?: { label: string; url: string }[];
}

const endorsements: Endorsement[] = [
  {
    name: 'Indivisible St. Peter/Greater Mankato',
    logo: '/indivisible.png',
    url: 'https://sites.google.com/indivisiblespgm.org/indivisiblespgm/about',
    body: [
      'Indivisible St. Peter/Greater Mankato, is a non-partisan, community group dedicated to positive, progressive action to make people’s lives better. They seek to create a more sustainable, equitable, and inclusive world by inspiring and empowering members to get involved in democracy and their communities.'
    ],
    links: [
      {
        label: 'Indivisible SPGM Primary Endorsements',
        url: 'https://sites.google.com/indivisiblespgm.org/indivisiblespgm/elections/2026-primary-endorsements'
      },
      {
        label: 'Indivisible SPGM Mayor Primary Voter Guide',
        url: 'https://sites.google.com/indivisiblespgm.org/indivisiblespgm/elections/2026-mankato-mayor-primary'
      }
    ]
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

    <p class="my-4 rounded-lg bg-sprout/50 p-4 text-center font-accent text-xl">
      Julia is grateful to be endorsed by:
    </p>

    <ul class="my-8 flex list-none flex-col gap-12 p-0">
      <li v-for="endorsement in endorsements" :key="endorsement.name">
        <div class="grid grid-cols-1 items-start gap-6 md:grid-cols-3">
          <a
            :href="endorsement.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block md:col-span-1"
          >
            <Image
              url-endpoint="https://ik.imagekit.io/voteforjulia"
              :src="endorsement.logo"
              :alt="`${endorsement.name} logo`"
              class="h-auto w-full"
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

          <div class="md:col-span-2">
            <h3>{{ endorsement.name }}</h3>
            <p v-for="(paragraph, index) in endorsement.body" :key="index">{{ paragraph }}</p>
            <ul v-if="endorsement.links" class="m-0 list-none p-0">
              <li v-for="link in endorsement.links" :key="link.url" class="mb-1">
                <a :href="link.url" target="_blank" rel="noopener noreferrer">{{ link.label }}</a>
              </li>
            </ul>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>
