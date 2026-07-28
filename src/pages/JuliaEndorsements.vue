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
    url: 'https://www.facebook.com/IndivisibleSPGM/posts/pfbid0MhUtKwfwrue3x8xXdrAhQdUDztbyohZRDAADa9k29Pha92fGxwjPxFSQ3htHAhual',
    body: [
      'I am so thankful for the official endorsement of Indivisible St. Peter/Greater Mankato!',
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

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-xl">
      Julia is grateful to be endorsed by:
    </p>

    <ul class="list-none p-0 my-8 flex flex-col gap-12">
      <li v-for="endorsement in endorsements" :key="endorsement.name">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
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

          <div class="md:col-span-2">
            <h3>{{ endorsement.name }}</h3>
            <p v-for="(paragraph, index) in endorsement.body" :key="index">{{ paragraph }}</p>
            <ul v-if="endorsement.links" class="list-none p-0 m-0">
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
