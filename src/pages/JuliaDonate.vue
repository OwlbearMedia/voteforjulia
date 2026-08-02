<script setup lang="ts">
import { onMounted } from 'vue';
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import { buildPageHead, campaignPersonNode, campaignWebSiteNode } from '../lib/pageHead';

defineOptions({
  name: 'JuliaDonate'
});

const DONORBOX_WIDGETS_SRC = 'https://donorbox.org/widgets.js';

/**
 * Donorbox owns this subtree, so we hand it over as raw markup rather than
 * rendering the tag through Vue.
 *
 * Vue creates elements with `document.createElement`, which runs a registered
 * custom element's constructor synchronously and then rejects the result if
 * that constructor gave itself attributes. Donorbox's does exactly that, so
 * the call fails with `NotSupportedError` and the visitor gets no donation
 * form. Assigning `innerHTML` parses the markup as a fragment instead, which
 * always takes the custom-element *upgrade* path — where a self-mutating
 * constructor is legal. It also keeps Vue out of the vendor's DOM, so the
 * shadow root and injected Stripe scripts can never read as a hydration
 * mismatch. See docs/donate-integration.md.
 */
const donorboxWidget =
  '<dbox-widget campaign="julia-hamann-for-mankato-mayor" type="donation_form" enable-auto-scroll="true"></dbox-widget>';

/**
 * Execute the loader only after hydration.
 *
 * From `<head>` it raced Vue: when the script won, it defined and upgraded
 * `<dbox-widget>` before hydration reached it, Vue read the vendor's mutations
 * as a mismatch, re-created the element via `createElement`, and the form died.
 * Running it here makes the order deterministic — the prerendered element is
 * always a plain, un-upgraded tag until Vue is done with it. The
 * `modulepreload` below keeps the download early, so only execution moves.
 */
onMounted(() => {
  if (document.querySelector(`script[src="${DONORBOX_WIDGETS_SRC}"]`)) return;

  const loader = document.createElement('script');
  loader.type = 'module';
  loader.async = true;
  loader.src = DONORBOX_WIDGETS_SRC;
  document.head.append(loader);
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
    // Warm the Donorbox loader during page load without executing it; the
    // onMounted hook above runs it once hydration is done. Deferring execution
    // is what removes the race, but deferring the download too would visibly
    // delay the form on mobile.
    extraLinks: [{ rel: 'modulepreload', href: DONORBOX_WIDGETS_SRC }],
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

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-xl">
      Donate now to help elect Julia as Mayor of Mankato!
    </p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-md:gap-y-4">
      <!-- `contents` keeps <dbox-widget> itself as the grid item. The markup is
           a module-level constant, never user input — see donorboxWidget. -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="contents" v-html="donorboxWidget"></div>

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
