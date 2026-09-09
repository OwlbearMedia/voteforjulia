<script setup lang="ts">
import { useHead } from '@unhead/vue';
import JuliaEndorsementCard from '../components/JuliaEndorsementCard.vue';
import type { Endorsement } from '../lib/endorsements';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaEndorsements'
});

const endorsements: Endorsement[] = [
  {
    name: 'Indivisible St. Peter/Greater Mankato',
    logo: '/indivisible.png',
    logoWidth: 960,
    logoHeight: 960,
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
  },
  {
    name: 'Run for Something',
    logo: '/run-for-something.jpg',
    logoWidth: 400,
    logoHeight: 400,
    url: 'https://www.runforsomething.net/',
    body: [
      'Run for Something is a national organization that recruits and supports the next generation of progressive leaders for state and local office.'
    ],
    links: [
      {
        label: 'Run for Something',
        url: 'https://runforsomething.net/'
      },
      {
        label: 'Julia Hamann Endorsement',
        url: 'https://directory.runforsomething.net/candidate/14077cfb2901e06d5815cceab4945a0c/hamann-julia/?fbclid=IwY2xjawTg2oVleHRuA2FlbQIxMABicmlkETFEa1VZUUVUbjAxcFo4dk5xc3J0YwZhcHBfaWQQMjIyMDM5MTc4ODIwMDg5MgABHjz5Kmf9CVbWyNZo2mjWlO78C9MTDH8mcWU9V_dtxkTHLQ6DIBKQfWrBvTDq_aem_CqWpu1RuExPVnpd9AMlwGA'
      }
    ]
  },
  {
    name: 'National Association of Social Workers - MN Chapter',
    logo: '/nasw-mn.jpeg',
    logoWidth: 447,
    logoHeight: 447,
    url: 'https://naswmn.socialworkers.org/About/What-We-Do',
    body: [
      "NASW's Minnesota Chapter (NASW-MN) currently maintains a membership base of nearly 2,000 professionally-trained social workers and students. Every year, they host a number of training and advocacy events around the state, including the Annual Conference, Social Work Summit, and Social Work Day at the Capitol. Their staff, interns, and volunteers work with community partners to promote practices and policies that align with social work ethics and values, and promote social justice."
    ],
    links: [
      {
        label: 'NASW-MN',
        url: 'https://naswmn.socialworkers.org/About/What-We-Do'
      }
    ]
  }
];

const supports: Endorsement[] = [
  {
    name: 'Blue Earth County DFL',
    logo: '/mn-dfl-logo.svg',
    logoWidth: 429,
    logoHeight: 184,
    url: 'https://cd1dfl.org/blue-earth',
    body: [
      'I am thankful for the letter of support for my campaign from the Blue Earth County DFL.',
      'As Mankato Mayor is a non-partisan position, this campaign is not associated with a specific political party, nor can the DFL extend official endorsement, but I am appreciative of their recognition, understanding the value of younger candidates with progressive values getting active in local politics.'
    ],
    links: [
      {
        label: 'Blue Earth County DFL',
        url: 'https://cd1dfl.org/blue-earth'
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
        <JuliaEndorsementCard :endorsement="endorsement" />
      </li>
    </ul>
  </section>

  <hr />

  <section id="letters-of-support">
    <h2>Letters of Support</h2>

    <ul class="my-8 flex list-none flex-col gap-12 p-0">
      <li v-for="support in supports" :key="support.name">
        <JuliaEndorsementCard :endorsement="support" />
      </li>
    </ul>
  </section>
</template>
