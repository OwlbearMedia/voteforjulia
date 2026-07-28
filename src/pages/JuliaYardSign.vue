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

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-xl">
      Yard signs are a great way to show your support and help spread the word about Julia’s
      campaign.
    </p>

    <div class="flex max-md:flex-col items-start gap-6 mb-4 *:flex-[1_1_50%] max-md:*:basis-auto">
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
        class="w-full h-auto rounded-lg"
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
