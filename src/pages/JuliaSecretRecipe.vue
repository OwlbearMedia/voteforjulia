<script setup lang="ts">
import { useHead } from '@unhead/vue'
import ShrimpSaladSupreme from '../assets/shrimp-salad-supreme.jpg';

defineOptions({
    name: 'JuliaSecretRecipe'
});

useHead({
  title: 'Secret Recipe | Julia Hamann for Mankato Mayor',
  link: [{
    rel: 'canonical',
    href: 'https://voteforjulia.com/secret-recipe'
  }],
  script: [{
    type: 'application/ld+json',
    textContent: JSON.stringify({
      '@context': 'https://schema.org',
      '@graph': [{
        '@type': 'WebSite',
        name: 'Vote for Julia Hamann',
        url: 'https://voteforjulia.com/'
      }, {
        '@type': 'Person',
        name: 'Julia Hamann',
        url: 'https://voteforjulia.com/',
        jobTitle: 'Candidate for Mayor of Mankato',
        description: 'Campaign website for Julia Hamann running for Mayor of Mankato.',
        address: {
          '@type': 'PostalAddress',
          addressLocality: 'Mankato',
          addressRegion: 'MN',
          addressCountry: 'US'
        },
        areaServed: {
          '@type': 'City',
          name: 'Mankato'
        },
        knowsAbout: [
          'Environmental justice',
          'Government transparency',
          'Affordable housing',
          'Community-led safety'
        ]
      }]
    })
  }],
  meta: [{
    name: 'description',
    content: 'Discover the secret recipe behind the Julia Hamann campaign for a more just, community-led Mankato.'
  }, {
    name: 'robots',
    content: 'index,follow'
  }, {
    property: 'og:type',
    content: 'website'
  }, {
    property: 'og:site_name',
    content: 'Vote for Julia'
  }, {
    property: 'og:title',
    content: 'Secret Recipe | Julia Hamann for Mankato Mayor'
  }, {
    property: 'og:description',
    content: 'Discover the secret recipe behind the Julia Hamann campaign for a more just, community-led Mankato.'
  }, {
    property: 'og:url',
    content: 'https://voteforjulia.com/secret-recipe'
  }, {
    property: 'og:image',
    content: 'https://voteforjulia.com/julia-social-banner.avif'
  }, {
    property: 'og:image:width',
    content: '200'
  }, {
    property: 'og:image:height',
    content: '93'
  }, {
    property: 'og:image:alt',
    content: 'Julia Hamann for Mankato Mayor campaign logo'
  }, {
    name: 'twitter:card',
    content: 'summary'
  }, {
    name: 'twitter:title',
    content: 'Secret Recipe | Julia Hamann for Mankato Mayor'
  }, {
    name: 'twitter:description',
    content: 'Discover the secret recipe behind the Julia Hamann campaign for a more just, community-led Mankato.'
  }, {
    name: 'twitter:image',
    content: 'https://voteforjulia.com/julia-social-banner.avif'
  }, {
    name: 'twitter:image:alt',
    content: 'Julia Hamann for Mankato Mayor campaign logo'
  }]
});
</script>

<template>
    <section id="secret-recipe">
        <h2>Shrimp Salad Supreme</h2>

        <p>
          Phylis Fisher, beloved grandmother, and active member of the Ladies'
          Aid organization of the Evangelical Lutheran Church of New Ulm,
          created the shrimp salad supreme. This delicious dish combines fresh
          canned shrimp, crisp vegetables, and a tangy dressing to create a meal
          that is both satisfying and inspiring. Just like Julia's vision for
          Mankato, this recipe brings together diverse ingredients to create
          something greater than the sum of its parts. Stay tuned for the full
          recipe and how it connects to Julia's campaign!
        </p>

        <div class="stances-layout">
          <ul>
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
          <img
            :src="ShrimpSaladSupreme"
            alt="Shrimp Salad Supreme - a secret recipe for Mankato's future"
            class="coming-soon"
            width="690"
            height="960"
            loading="lazy"
            decoding="async"
          />
        </div>

        <p>
          Mix the lemon Jello with the boiling water. Let stand until it
          congeals. Mix together the whipped cream, mayonnaise, and cream
          cheese. Whip Jello and add the second mixture; also add the eggs,
          celery, green pepper, onion, shrimp, and salt with a few chopped
          stuffed olives. Mix and put into mold. Chill until firm. Unmold
          garnish with lettuce and top with chopped olives.
        </p>
      </section>
</template>