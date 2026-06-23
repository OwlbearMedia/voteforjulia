<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { RouterLink } from 'vue-router';
import { Image } from '@imagekit/vue';
import JuliaContactForm from '../components/JuliaContactForm.vue';

defineOptions({
  name: 'JuliaHome'
});

useHead({
  title: 'Home | Julia Hamann for Mankato Mayor',
  link: [
    {
      rel: 'canonical',
      href: 'https://voteforjulia.com/'
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
        'Vote for Julia Hamann for Mayor of Mankato. Explore priorities on transparency, sustainability, affordability, community safety, and ways to volunteer.'
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
      content: 'Julia Hamann for Mankato Mayor'
    },
    {
      property: 'og:description',
      content:
        'Learn about Julia Hamann and her campaign for Mayor of Mankato with a vision for equity, transparency, sustainability, and community-led safety.'
    },
    {
      property: 'og:url',
      content: 'https://voteforjulia.com/'
    },
    {
      property: 'og:image',
      content: 'https://voteforjulia.com/julia-social-banner.avif'
    },
    {
      property: 'og:image:width',
      content: '200'
    },
    {
      property: 'og:image:height',
      content: '93'
    },
    {
      property: 'og:image:alt',
      content: 'Julia Hamann for Mankato Mayor campaign logo'
    },
    {
      name: 'twitter:card',
      content: 'summary'
    },
    {
      name: 'twitter:title',
      content: 'Julia Hamann for Mankato Mayor'
    },
    {
      name: 'twitter:description',
      content:
        'Learn about Julia Hamann and her campaign for Mayor of Mankato with a vision for equity, transparency, sustainability, and community-led safety.'
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
  <section id="home">
    <div class="hero">
      <Image
        url-endpoint="https://ik.imagekit.io/voteforjulia"
        src="/julia-hero.webp"
        class="hero-image"
        sizes="(max-width: 700px) calc(100vw - 2.5rem), 960px"
        :image-breakpoints="[320, 390, 430, 520, 640, 780, 960, 1440, 1920]"
        :device-breakpoints="[]"
        width="960"
        height="672"
        alt="Julia Hamann for Mankato Mayor"
        crossorigin="anonymous"
        fetchpriority="high"
        loading="eager"
      />
    </div>

    <p class="bigger">
      Julia is a progressive, passionate, and present leader. She cares deeply about building a
      community where everyone can live a life of dignity, respect, and freedom.
    </p>
    <p class="bigger">
      Julia is running for Mayor of Mankato because she’s frustrated with the status quo. She
      understands the experience of everyday Mankatoans and thinks our local government could be
      doing better by our community members.
    </p>
  </section>

  <section id="meet-julia">
    <h2>Meet Julia</h2>
    <p>
      Julia is a proud Mankato “townie” through and through. As a lifelong Mankato resident, Julia
      is committed to giving back to the community that has nurtured her.
    </p>
    <p>
      Julia is running for Mayor to change the conversation at City Council - to center the
      conversation around the real-life experiences of people in our town. As a social worker,
      renter, queer woman, survivor of gender-based violence, millennial, and auntie, she
      understands the challenges many people in Mankato face and believes everyone should be heard
      and respected - especially those too often left out of decision making.
    </p>
    <p>
      Her guiding values include equity, accountability, transparency, dignity, justice, freedom,
      growth, and community.
    </p>
    <div>
      <RouterLink class="btn" to="/meet-julia"> Learn more about Julia </RouterLink>
    </div>
  </section>

  <hr />

  <section id="issues">
    <div class="issues-layout">
      <div class="issues-text issues-text-centered">
        <h2 class="issues-header">Issues</h2>
        <p>
          As mayor, Julia knows she can’t singlehandedly change city policy overnight, but she can
          promise to show up, ask hard questions, bring new ideas to the table, and challenge the
          status quo.
        </p>
        <p class="card">
          Julia wants to start new conversations about issues our town cares about.
        </p>
      </div>
      <div>
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/julia-blue-sky.webp"
          class="coming-soon"
          sizes="(max-width: 700px) calc(100vw - 2.5rem), 250px"
          :image-breakpoints="[180, 250, 320, 390, 500]"
          :device-breakpoints="[]"
          width="390"
          height="517"
          alt="Julia Hamann for Mankato Mayor"
          crossorigin="anonymous"
          loading="lazy"
          decoding="async"
        />
      </div>
    </div>

    <hr />

    <h3>Community Input and Transparency</h3>
    <p class="card">
      Julia wants to ensure that citizens are listened to and that city government remains
      transparent and accountable to the community.
    </p>
    <p>
      She hopes to create more opportunities for open dialogue between the City Council and Mankato
      residents by exploring new ways to gather feedback from citizens, especially from those most
      impacted by decisions and voices often left out of conversations. She wants to increase
      transparency in the council’s decision-making processes and ensure that the council is
      responsive and respectful to feedback and ideas from their constituents.
    </p>

    <hr />

    <h3>Affordability and Tenants Rights</h3>
    <p class="card">
      Julia understands that Mankato citizens are experiencing serious financial strain and the gap
      between the richest and most impoverished individuals is growing.
    </p>
    <p>
      Julia plans to re-examine how the city defines affordable housing and invests in the creation
      of more affordable units. She is also committed to ensuring fair and just rental practices.
      She’s interested in exploring ways city policy can support businesses in paying living wage.
    </p>

    <hr />

    <h3>Reimagining Public Safety</h3>
    <p class="card">
      Julia believes that safety for citizens goes far beyond law enforcement and emergency
      services.
    </p>
    <p>
      Community safety is achieved through a strong social safety network where citizens have access
      to resources beyond police intervention. When people have access to safe housing, financial
      stability, and community support systems that help prevent crises before they happen,
      communities thrive. Julia supports strengthening partnerships with local social service
      organizations and reviewing the city’s ordinances that criminalize homelessness.
    </p>

    <hr />

    <h3>Environmental Justice and Sustainability</h3>
    <p class="card">
      Julia wants to bring new conversations to the city council about how we can sustain a healthy
      future for Mankato by examining how proposed developments, like data centers, might impact our
      environment.
    </p>
    <p>
      Julia understands it is our responsibility as humans to care for our environment and to be
      proactive about safeguarding our climate for future generations. She is supportive of the
      city's climate action plan and wants to ensure that we continue to take steps locally to be
      resilient in the face of climate change. Julia is inspired by cities who prioritize the
      environment through policies that support green infrastructure development and de-incentivize
      harmful practices, such as a plastic bag fee.
    </p>
  </section>

  <hr />

  <section id="volunteer">
    <h2>Volunteer</h2>

    <div class="stances-layout">
      <div class="stances-text">
        <p>Join the campaign team to help with outreach, events, and voter engagement.</p>
        <JuliaContactForm />
      </div>
      <div>
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/julia.avif"
          alt="Julia Hamann for Mankato Mayor"
          class="coming-soon"
          sizes="(max-width: 700px) calc(100vw - 2.5rem), 420px"
          :image-breakpoints="[240, 320, 390, 420, 560]"
          :device-breakpoints="[]"
          width="390"
          height="390"
          crossorigin="anonymous"
          loading="lazy"
          decoding="async"
        />
      </div>
    </div>
  </section>
</template>
