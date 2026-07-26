<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import JuliaYardSignForm from '../components/JuliaYardSignForm.vue';

defineOptions({
  name: 'JuliaYardSign'
});

useHead({
  title: 'Yard Sign | Julia Hamann for Mankato Mayor',
  link: [
    {
      rel: 'canonical',
      href: 'https://voteforjulia.com/yard-signs'
    }
  ],
  script: [
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
      content: 'Request a yard sign to show your support for Julia Hamann for Mankato Mayor.'
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
      property: 'og:site_name',
      content: 'Vote for Julia'
    },
    {
      property: 'og:title',
      content: 'Yard Sign | Julia Hamann for Mankato Mayor'
    },
    {
      property: 'og:description',
      content: 'Request a yard sign to show your support for Julia Hamann for Mankato Mayor.'
    },
    {
      property: 'og:url',
      content: 'https://voteforjulia.com/yard-signs'
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
      content: 'Yard Sign | Julia Hamann for Mankato Mayor'
    },
    {
      name: 'twitter:description',
      content: 'Request a yard sign to show your support for Julia Hamann for Mankato Mayor.'
    },
    {
      name: 'twitter:image',
      content: 'https://voteforjulia.com/julia-social-banner.avif'
    },
    {
      name: 'twitter:image:alt',
      content: 'Julia Hamann for Mankato Mayor campaign logo'
    }
  ]
});
</script>

<template>
  <section id="yard-sign">
    <h2>Get a Yard Sign Today!</h2>

    <p class="font-accent bg-sprout/50 p-4 my-4 text-center rounded-lg text-[1.25rem]">
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
