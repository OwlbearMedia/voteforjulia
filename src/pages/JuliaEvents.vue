<script setup lang="ts">
import { useHead } from '@unhead/vue';
import IconLocation from '../components/icons/IconLocation.vue';

defineOptions({
  name: 'JuliaEvents'
});

useHead({
  title: 'Events | Julia Hamann for Mankato Mayor',
  link: [
    {
      rel: 'canonical',
      href: 'https://voteforjulia.com/events'
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
        'Find upcoming events for the Julia Hamann campaign — town halls, canvasses, and community meetups in Mankato.'
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
      content: 'Events | Julia Hamann for Mankato Mayor'
    },
    {
      property: 'og:description',
      content:
        'Find upcoming events for the Julia Hamann campaign — town halls, canvasses, and community meetups in Mankato.'
    },
    {
      property: 'og:url',
      content: 'https://voteforjulia.com/events'
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
      content: 'Events | Julia Hamann for Mankato Mayor'
    },
    {
      name: 'twitter:description',
      content:
        'Find upcoming events for the Julia Hamann campaign — town halls, canvasses, and community meetups in Mankato.'
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
  <section id="events">
    <h2>Upcoming Events</h2>

    <p>Check out our latest events below:</p>

    <div class="event">
      <div class="event-heading">
        <h3>Campaign Launch Party!</h3>
        <p class="event-date">Monday, June 29 at 5:30 &ndash; 9pm</p>
        <a class="event-location" href="https://maps.app.goo.gl/bE9THdo92AbrKKeJ7" target="_blank">
          <IconLocation /> Mankato Makerspace, 1700 3rd Ave</a
        >
      </div>

      <hr />

      <div>
        <p>
          Join us for a launch party to celebrate campaign season kick off and build momentum for
          the primary on August 11th!
        </p>
        <p>
          Connect with candidate Julia Hamann for Mankato Mayor and show your support for the
          campaign!
        </p>

        <dl>
          <dt>5:30PM</dt>
          <dd>Social hour - Mingle, snack, &amp; craft</dd>

          <dt>6:45PM</dt>
          <dd>Candidate speeches</dd>

          <dt>7:00PM</dt>
          <dd>Music by Ark &amp; Grum</dd>

          <dt>8:00PM</dt>
          <dd>Music by Laura Schultz &amp; Colin Scharf</dd>
        </dl>

        <ul>
          <li>
            <div>
              <span class="event-highlight">Make your own campaign swag</span><br />
              Screen printing, button making, &amp; block printing
            </div>
          </li>
          <li>
            <div>
              <span class="event-highlight">Support the campaign</span><br />
              Donate, volunteer, yard signs, &amp; campaign lit
            </div>
          </li>
        </ul>

        <p>
          <a href="https://www.facebook.com/foodnotbombs.mankato" target="_blank">Food Not Bombs</a>
          will also be collecting in kind donations of tote bags, reusable water bottles, shelf
          stable snack items and travel hygiene items to support the group's mutual aide efforts. A
          list of needed items will be posted in the event thread.
        </p>
      </div>
    </div>

    <div class="event">
      <div class="event-heading">
        <h3>Primary Election Day!</h3>
        <div class="event-date">August 11, 2026</div>
      </div>

      <hr />

      <p>
        Check your voter registration:
        <a href="https://www.sos.mn.gov/elections-voting/register-to-vote/" target="_blank"
          >https://www.sos.mn.gov/elections-voting/register-to-vote/</a
        >
      </p>
      <p>
        Find your polling place:
        <a href="https://www.sos.mn.gov/elections-voting/election-day-voting" target="_blank"
          >https://www.sos.mn.gov/elections-voting/election-day-voting</a
        >
      </p>
    </div>
  </section>
</template>
