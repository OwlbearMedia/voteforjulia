<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import JuliaYardSignForm from '../components/JuliaYardSignForm.vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaYardSign'
});

useHead(
  buildPageHead({
    path: '/yard-signs',
    title: 'Yard Sign | Julia Hamann for Mankato Mayor',
    description: 'Request a yard sign to show your support for Julia Hamann for Mankato Mayor.'
  })
);
</script>

<template>
  <section id="yard-sign">
    <h2>Get a Yard Sign Today!</h2>

    <p class="my-4 rounded-lg bg-sprout/50 p-4 text-center font-accent text-xl">
      Yard signs are a great way to show your support and help spread the word about Julia’s
      campaign.
    </p>

    <div
      class="mb-4 flex items-start gap-6 *:flex-1 *:basis-1/2 max-md:flex-col max-md:*:basis-auto"
    >
      <div>
        <p>
          As a grassroots campaign, every dollar makes a significant impact. We’re asking for a $10
          minimum sign contribution to help cover costs, and a $20 suggested donation to help us
          spread our reach to voters.
        </p>

        <JuliaYardSignForm />
      </div>
      <Image
        url-endpoint="https://ik.imagekit.io/voteforjulia"
        src="/yard-sign.webp"
        alt="Yard sign for Julia Hamann for Mankato Mayor"
        class="h-auto w-full rounded-lg"
        sizes="(max-width: 767px) calc(100vw - 2.5rem), (max-width: 960px) calc((100vw - 5.5rem) / 2), 436px"
        :image-breakpoints="[240, 320, 420, 560, 767, 872, 1200]"
        :device-breakpoints="[]"
        width="1200"
        height="1481"
        crossorigin="anonymous"
        loading="lazy"
        decoding="async"
      />
    </div>
  </section>
</template>
