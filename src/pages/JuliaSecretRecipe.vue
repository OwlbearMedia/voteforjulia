<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaSecretRecipe'
});

useHead(
  buildPageHead({
    path: '/secret-recipe',
    title: 'Secret Recipe | Julia Hamann for Mankato Mayor',
    description:
      'Discover the secret recipe behind the Julia Hamann campaign for a more just, community-led Mankato.'
  })
);
</script>

<template>
  <section id="secret-recipe">
    <h2>Shrimp Salad Supreme</h2>

    <p>
      Phylis Fisher, beloved grandmother, and active member of the Ladies' Aid organization of the
      Evangelical Lutheran Church of New Ulm, created the shrimp salad supreme. This delicious dish
      combines fresh canned shrimp, crisp vegetables, and a tangy dressing to create a meal that is
      both satisfying and inspiring. Just like Julia's vision for Mankato, this recipe brings
      together diverse ingredients to create something greater than the sum of its parts. Stay tuned
      for the full recipe and how it connects to Julia's campaign!
    </p>

    <div class="flex max-md:flex-col items-start gap-6 mb-4 *:flex-[1_1_50%] max-md:*:basis-auto">
      <ul class="list-disc pl-5 m-0">
        <li>1 pkg. lemon Jello</li>
        <li>1 cup boiling water</li>
        <li>1/2 cup whipped cream</li>
        <li>1/2 cup mayonnaise</li>
        <li>3 oz package cream cheese</li>
        <li>3 hard boiled eggs, chopped</li>
        <li>1 1/2 cup chopped celery</li>
        <li>1 tbsp. chopped green pepper</li>
        <li>3 tbsp. chopped onion</li>
        <li>1 can shrimp, drained</li>
        <li>1 tsp. salt</li>
      </ul>
      <Image
        url-endpoint="https://ik.imagekit.io/voteforjulia"
        src="/shrimp-salad-supreme.jpg"
        alt="Shrimp Salad Supreme - a secret recipe for Mankato's future"
        class="w-full h-auto rounded-lg"
        sizes="(max-width: 767px) calc(100vw - 2.5rem), (max-width: 960px) calc((100vw - 5.5rem) / 2), 436px"
        :image-breakpoints="[240, 320, 420, 540]"
        :device-breakpoints="[]"
        width="540"
        height="360"
        crossorigin="anonymous"
        loading="lazy"
        decoding="async"
      />
    </div>

    <p>
      Mix the lemon Jello with the boiling water. Let stand until it congeals. Mix together the
      whipped cream, mayonnaise, and cream cheese. Whip Jello and add the second mixture; also add
      the eggs, celery, green pepper, onion, shrimp, and salt with a few chopped stuffed olives. Mix
      and put into mold. Chill until firm. Unmold garnish with lettuce and top with chopped olives.
    </p>
  </section>
</template>
