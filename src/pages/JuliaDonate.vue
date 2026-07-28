<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import { buildPageHead, campaignPersonNode, campaignWebSiteNode } from '../lib/pageHead';

defineOptions({
  name: 'JuliaDonate'
});

const donateDescription =
  'Support Julia Hamann in her campaign for Mayor of Mankato by making a donation. Every contribution helps build a more just, community-led Mankato.';

useHead(
  buildPageHead({
    path: '/donate',
    title: 'Donate | Julia Hamann for Mankato Mayor',
    description: donateDescription,
    keywords:
      'Julia Hamann donation, Mankato mayor campaign donation, donate to Julia Hamann, Vote for Julia',
    // Donorbox loader must run before the JSON-LD script; buildPageHead keeps
    // `scripts` ahead of the generated ld+json entry.
    scripts: [
      {
        type: 'module',
        src: 'https://donorbox.org/widgets.js',
        async: true
      }
    ],
    // Custom graph so the WebPage node sits between WebSite and Person.
    schemaGraph: [
      campaignWebSiteNode,
      {
        '@type': 'WebPage',
        name: 'Donate | Julia Hamann for Mankato Mayor',
        url: 'https://voteforjulia.com/donate',
        description:
          'Support Julia Hamann in her campaign for Mayor of Mankato by making a donation.',
        isPartOf: {
          '@type': 'WebSite',
          name: 'Vote for Julia Hamann',
          url: 'https://voteforjulia.com/'
        },
        about: {
          '@type': 'Person',
          name: 'Julia Hamann'
        },
        potentialAction: {
          '@type': 'DonateAction',
          target: 'https://voteforjulia.com/donate'
        }
      },
      campaignPersonNode
    ],
    extraMeta: [
      { property: 'og:locale', content: 'en_US' },
      { name: 'twitter:url', content: 'https://voteforjulia.com/donate' }
    ]
  })
);
</script>

<template>
  <section id="donate">
    <h2>Donate</h2>

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-[1.25rem]">
      Donate now to help elect Julia as Mayor of Mankato!
    </p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-md:gap-y-4">
      <dbox-widget
        campaign="julia-hamann-for-mankato-mayor"
        type="donation_form"
        enable-auto-scroll="true"
      ></dbox-widget>

      <div class="max-md:contents">
        <p class="max-md:order-first max-md:mb-0">
          Julia is running a true grassroots campaign, for and by the community! Every contribution
          makes a meaningful impact, whether it's $20, $100, or more. Your donation will help us
          print materials, host events, knock on doors, and reach voters.
        </p>

        <p class="max-md:order-first max-md:mb-0">
          Mankato donors can also get a yard sign. If you would like a yard sign write "yard sign"
          in the comment section when making your donation then
          <RouterLink to="/yard-signs">fill out this form</RouterLink>. We will be in touch soon!
        </p>

        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/julia-rect.webp"
          alt="Julia Hamann, starting a new conversation as Mayor of Mankato"
          class="w-full h-auto rounded-lg shadow-soft"
          sizes="(max-width: 767px) calc(100vw - 2.5rem), (max-width: 960px) calc((100vw - 6rem) / 2), 432px"
          :image-breakpoints="[240, 320, 420, 560, 600]"
          :device-breakpoints="[]"
          width="600"
          height="470"
          crossorigin="anonymous"
          decoding="async"
        />
      </div>
    </div>
    <hr />
  </section>
</template>
