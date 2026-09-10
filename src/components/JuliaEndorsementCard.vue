<script setup lang="ts">
import { computed } from 'vue';
import { Image } from '@imagekit/vue';
import { type Endorsement, logoBreakpoints } from '../lib/endorsements';

defineOptions({
  name: 'JuliaEndorsementCard'
});

const props = defineProps<{ endorsement: Endorsement }>();

const breakpoints = computed(() => logoBreakpoints(props.endorsement.logoWidth));
</script>

<template>
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
        :image-breakpoints="breakpoints"
        :device-breakpoints="[]"
        :width="endorsement.logoWidth"
        :height="endorsement.logoHeight"
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
</template>
