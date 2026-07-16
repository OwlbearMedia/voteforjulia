<script setup lang="ts">
import { useHead } from '@unhead/vue';
import { Image } from '@imagekit/vue';
import IconCalendar from '../components/icons/IconCalendar.vue';

defineOptions({
  name: 'JuliaNews'
});

useHead({
  title: 'News | Julia Hamann for Mankato Mayor',
  link: [
    {
      rel: 'canonical',
      href: 'https://voteforjulia.com/news'
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
          },
          {
            '@type': 'NewsArticle',
            headline: 'Candidate for Mankato Mayor Hosts Campaign Launch Party',
            datePublished: '2026-06-29',
            author: {
              '@type': 'Person',
              name: 'Kate Jones'
            },
            publisher: {
              '@type': 'Organization',
              name: 'KEYC'
            },
            url: 'https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/',
            about: {
              '@type': 'Person',
              name: 'Julia Hamann'
            }
          },
          {
            '@type': 'NewsArticle',
            headline: 'RACE TO WATCH: Hamann hopes to bring conversation to City Council',
            datePublished: '2026-06-08',
            author: {
              '@type': 'Person',
              name: 'Ethan Becker'
            },
            publisher: {
              '@type': 'Organization',
              name: 'Mankato Free Press'
            },
            url: 'https://www.mankatofreepress.com/news/local_news/race-to-watch-hamann-hopes-to-bring-conversation-to-city-council/article_167d04f5-3f33-4b85-a921-8e6e72a43b16.html',
            about: {
              '@type': 'Person',
              name: 'Julia Hamann'
            }
          },
          {
            '@type': 'VideoObject',
            name: 'RACE TO WATCH: Julia Hamann',
            uploadDate: '2026-06-25',
            description:
              'We sat down with candidate for Mankato mayor Julia Hamann to discuss her campaign and her stances on important issues to the city.',
            thumbnailUrl: 'https://i.ytimg.com/vi/UnVrel_BRfs/hqdefault.jpg',
            publisher: {
              '@type': 'Organization',
              name: 'Mankato Free Press'
            },
            url: 'https://www.youtube.com/watch?v=UnVrel_BRfs',
            about: {
              '@type': 'Person',
              name: 'Julia Hamann'
            }
          },
          {
            '@type': 'NewsArticle',
            headline:
              'Mankato candidates officially file for office, with passing of Tuesday deadline',
            datePublished: '2026-06-03',
            author: {
              '@type': 'Person',
              name: 'Aaron Stuve'
            },
            publisher: {
              '@type': 'Organization',
              name: 'KEYC'
            },
            url: 'https://www.keyc.com/2026/06/03/mankato-candidates-file-office/',
            about: {
              '@type': 'Person',
              name: 'Julia Hamann'
            }
          },
          {
            '@type': 'NewsArticle',
            headline: 'Hamann, Bases look to bring new conversations to Mankato leadership',
            datePublished: '2026-05-30',
            author: {
              '@type': 'Person',
              name: 'Ethan Becker'
            },
            publisher: {
              '@type': 'Organization',
              name: 'Mankato Free Press'
            },
            url: 'https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html',
            about: {
              '@type': 'Person',
              name: 'Julia Hamann'
            }
          }
        ]
      })
    }
  ],
  meta: [
    {
      name: 'description',
      content: "Read the latest news coverage of Julia Hamann's campaign for Mankato Mayor."
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
      content: 'News | Julia Hamann for Mankato Mayor'
    },
    {
      property: 'og:description',
      content: "Read the latest news coverage of Julia Hamann's campaign for Mankato Mayor."
    },
    {
      property: 'og:url',
      content: 'https://voteforjulia.com/news'
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
      content: 'News | Julia Hamann for Mankato Mayor'
    },
    {
      name: 'twitter:description',
      content: "Read the latest news coverage of Julia Hamann's campaign for Mankato Mayor."
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
  <section id="news">
    <h2>Julia in the news</h2>

    <p>Check out the latest coverage of Julia's campaign:</p>

    <div class="event">
      <div class="event-heading">
        <h3>Candidate for Mankato Mayor Hosts Campaign Launch Party</h3>
        <a
          class="event-date"
          href="https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> June 29, 2026 &middot; KEYC</a
        >
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/launch-party.jpg"
          class="hero-image"
          sizes="(max-width: 700px) calc(100vw - 2.5rem), 960px"
          :image-breakpoints="[320, 390, 430, 520, 640, 780, 960, 1440, 1920]"
          :device-breakpoints="[]"
          width="960"
          height="672"
          alt="Julia Hamann for Mankato Mayor Launch Party"
          crossorigin="anonymous"
          fetchpriority="high"
          loading="eager"
        />
      </div>
      <p>
        Julia's campaign launch party at The Makerspace drew more than 100 attendees for
        button-making, screen printing, and live music. Guests connected directly with Julia,
        chipped in donations for Food Not Bombs, and picked up $10 yard signs to show their support
        ahead of the August 11th primary.
      </p>
      <p>
        <a
          href="https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/"
          target="_blank"
          rel="noopener noreferrer"
          >Read the full article at KEYC</a
        >
      </p>
    </div>

    <div class="event">
      <div class="event-heading">
        <h3>RACE TO WATCH: Julia Hamann</h3>
        <a
          class="event-date"
          href="https://www.youtube.com/watch?v=UnVrel_BRfs"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> June 25, 2026 &middot; Mankato Free Press</a
        >
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          src="/race-to-watch.jpeg"
          class="hero-image"
          sizes="(max-width: 700px) calc(100vw - 2.5rem), 960px"
          :image-breakpoints="[320, 390, 430, 520, 640, 780, 960, 1440, 1920]"
          :device-breakpoints="[]"
          width="960"
          height="672"
          alt="Julia Hamann for Mankato Mayor Interview"
          crossorigin="anonymous"
          fetchpriority="high"
          loading="eager"
        />
      </div>
      <p>
        Julia sat down with the Mankato Free Press to discuss her campaign and her stances on the
        issues that matter most to the city.
      </p>
      <p>
        <a
          href="https://www.youtube.com/watch?v=UnVrel_BRfs"
          target="_blank"
          rel="noopener noreferrer"
          >Watch the video on YouTube</a
        >
      </p>
    </div>

    <div class="event">
      <div class="event-heading">
        <h3>RACE TO WATCH: Hamann hopes to bring conversation to City Council</h3>
        <a
          class="event-date"
          href="https://www.mankatofreepress.com/news/local_news/race-to-watch-hamann-hopes-to-bring-conversation-to-city-council/article_167d04f5-3f33-4b85-a921-8e6e72a43b16.html"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> June 8, 2026 &middot; Mankato Free Press</a
        >
      </div>

      <hr />

      <p>
        In this "Race to Watch" profile, the Mankato Free Press explored Julia's approach heading
        into the primary against incumbent Najwa Massad and challenger Toby Leonard. Rather than
        leading with a fixed policy platform, Julia emphasized bringing more community conversation
        into City Council decisions &mdash; including participatory budgeting, stronger tenant
        protections, and a careful look at data center development.
      </p>
      <p>
        <a
          href="https://www.mankatofreepress.com/news/local_news/race-to-watch-hamann-hopes-to-bring-conversation-to-city-council/article_167d04f5-3f33-4b85-a921-8e6e72a43b16.html"
          target="_blank"
          rel="noopener noreferrer"
          >Read the full article at Mankato Free Press</a
        >
      </p>
    </div>

    <div class="event">
      <div class="event-heading">
        <h3>Mankato candidates officially file for office, with passing of Tuesday deadline</h3>
        <a
          class="event-date"
          href="https://www.keyc.com/2026/06/03/mankato-candidates-file-office/"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> June 3, 2026 &middot; KEYC</a
        >
      </div>

      <hr />

      <p>
        Tuesday marked the filing deadline for Minnesota candidates across local, state, and federal
        races. In Mankato's mayoral contest, incumbent Mayor Najwa Massad is seeking her third term,
        facing challengers Toby Leonard and Julia, who is making a push through a grassroots
        campaign. An August primary will narrow the mayoral field to two candidates before the
        November general election.
      </p>
      <p>
        <a
          href="https://www.keyc.com/2026/06/03/mankato-candidates-file-office/"
          target="_blank"
          rel="noopener noreferrer"
          >Read the full article at KEYC</a
        >
      </p>
    </div>

    <div class="event">
      <div class="event-heading">
        <h3>Hamann, Bases look to bring new conversations to Mankato leadership</h3>
        <a
          class="event-date"
          href="https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> May 30, 2026 &middot; Mankato Free Press</a
        >
      </div>

      <hr />

      <p>
        This profile looks at Julia, 33, and Jacob Bases, 37, who is running for the Ward 3 City
        Council seat &mdash; both of whom would be among the youngest members of Mankato's
        leadership if elected. Julia discussed how her age and background in social services shape
        her perspective on rental equity, public safety reform, and environmental justice.
      </p>
      <p>
        <a
          href="https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html"
          target="_blank"
          rel="noopener noreferrer"
          >Read the full article at Mankato Free Press</a
        >
      </p>
    </div>
  </section>
</template>
