<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';

defineOptions({
  name: 'JuliaDonate'
});

useHead({
  title: 'Donate | Julia Hamann for Mankato Mayor',
  link: [
    {
      rel: 'canonical',
      href: 'https://voteforjulia.com/donate'
    }
  ],
  script: [
    {
      type: 'module',
      src: 'https://donorbox.org/widgets.js',
      async: true
    },
    {
      type: 'application/ld+json',
      textContent: JSON.stringify({
        '@context': 'https://schema.org',
        '@graph': [
          {
            '@type': 'WebSite',
            name: 'Vote for Julia Hamann',
            url: 'https://voteforjulia.com/'
          },
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
          {
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
            ],
            sameAs: [
              'https://www.facebook.com/profile.php?id=61590411090366',
              'https://www.instagram.com/voteforjuliahamann/'
            ]
          }
        ]
      })
    }
  ],
  meta: [
    {
      name: 'description',
      content:
        'Support Julia Hamann in her campaign for Mayor of Mankato by making a donation. Every contribution helps build a more just, community-led Mankato.'
    },
    {
      name: 'keywords',
      content:
        'Julia Hamann donation, Mankato mayor campaign donation, donate to Julia Hamann, Vote for Julia'
    },
    {
      name: 'robots',
      content: 'index,follow'
    },
    {
      property: 'og:type',
      content: 'website'
    },
    {
      property: 'og:locale',
      content: 'en_US'
    },
    {
      property: 'og:site_name',
      content: 'Vote for Julia'
    },
    {
      property: 'og:title',
      content: 'Donate | Julia Hamann for Mankato Mayor'
    },
    {
      property: 'og:description',
      content:
        'Support Julia Hamann in her campaign for Mayor of Mankato by making a donation. Every contribution helps build a more just, community-led Mankato.'
    },
    {
      property: 'og:url',
      content: 'https://voteforjulia.com/donate'
    },
    {
      property: 'og:image',
      content: 'https://voteforjulia.com/julia-social-banner.avif'
    },
    {
      property: 'og:image:width',
      content: '1200'
    },
    {
      property: 'og:image:height',
      content: '583'
    },
    {
      property: 'og:image:alt',
      content: 'Julia Hamann for Mankato Mayor campaign logo'
    },
    {
      name: 'twitter:card',
      content: 'summary_large_image'
    },
    {
      name: 'twitter:title',
      content: 'Donate | Julia Hamann for Mankato Mayor'
    },
    {
      name: 'twitter:description',
      content:
        'Support Julia Hamann in her campaign for Mayor of Mankato by making a donation. Every contribution helps build a more just, community-led Mankato.'
    },
    {
      name: 'twitter:image',
      content: 'https://voteforjulia.com/julia-social-banner.avif'
    },
    {
      name: 'twitter:url',
      content: 'https://voteforjulia.com/donate'
    },
    {
      name: 'twitter:image:alt',
      content: 'Julia Hamann for Mankato Mayor campaign logo'
    }
  ]
});
</script>

<template>
  <section id="donate">
    <h2>Donate</h2>

    <p class="card">Donate now to help elect Julia as Mayor of Mankato!</p>

    <div class="donate-layout">
      <dbox-widget
        campaign="julia-hamann-for-mankato-mayor"
        type="donation_form"
        enable-auto-scroll="true"
      ></dbox-widget>

      <div class="donate-text">
        <p>
          Julia is running a true grassroots campaign, for and by the community! Every contribution
          makes a meaningful impact, whether it's $20, $100, or more. Your donation will help us
          print materials, host events, knock on doors, and reach voters.
        </p>
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/julia-rect.webp"
          alt="Julia Hamann, starting a new conversation as Mayor of Mankato"
          class="hero-image"
          sizes="(max-width: 700px) calc(100vw - 2.5rem), 420px"
          :image-breakpoints="[240, 320, 420, 560, 800]"
          :device-breakpoints="[]"
          crossorigin="anonymous"
          decoding="async"
        />
      </div>
    </div>
    <hr />
  </section>
</template>
