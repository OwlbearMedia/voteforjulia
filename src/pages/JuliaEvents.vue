<script setup lang="ts">
import { useHead } from '@unhead/vue';
import IconLocation from '../components/icons/IconLocation.vue';
import IconCalendar from '../components/icons/IconCalendar.vue';

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
          },
          {
            '@type': 'Event',
            name: 'Campaign Launch Party!',
            description:
              'A launch party to celebrate campaign season kick off and build momentum for the primary on August 11th. Connect with candidate Julia Hamann for Mankato Mayor, with candidate speeches, live music, campaign swag-making, and light refreshments by Food Not Bombs.',
            startDate: '2026-06-29T17:30:00-05:00',
            endDate: '2026-06-29T21:00:00-05:00',
            eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
            eventStatus: 'https://schema.org/EventScheduled',
            url: 'https://www.facebook.com/events/1000640362322768',
            location: {
              '@type': 'Place',
              name: 'Mankato Makerspace',
              address: {
                '@type': 'PostalAddress',
                streetAddress: '1700 3rd Ave',
                addressLocality: 'Mankato',
                addressRegion: 'MN',
                addressCountry: 'US'
              }
            },
            organizer: {
              '@type': 'Person',
              name: 'Julia Hamann',
              url: 'https://voteforjulia.com/'
            },
            performer: [
              { '@type': 'MusicGroup', name: 'Ark & Grum' },
              { '@type': 'Person', name: 'Laura Schultz' },
              { '@type': 'Person', name: 'Colin Scharf' }
            ]
          },
          {
            '@type': 'Event',
            name: 'Primary Election Day',
            description:
              'Minnesota primary election day. Check your voter registration and find your polling place to vote in the Mankato mayoral primary.',
            startDate: '2026-08-11',
            eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
            eventStatus: 'https://schema.org/EventScheduled',
            url: 'https://voteforjulia.com/events',
            location: {
              '@type': 'Place',
              name: 'Mankato, Minnesota',
              address: {
                '@type': 'PostalAddress',
                addressLocality: 'Mankato',
                addressRegion: 'MN',
                addressCountry: 'US'
              }
            }
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

    <p>Check out upcoming events below:</p>

    <div class="event">
      <div class="event-heading">
        <h3>Primary Election Day!</h3>
        <a
          class="event-date"
          href="https://www.sos.mn.gov/elections-voting/election-day-voting"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> August 11, 2026</a
        >
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

  <section id="past-events">
    <h2>Past Events</h2>

    <div class="event">
      <div class="event-heading">
        <h3>Campaign Launch Party!</h3>
        <div>
          <a
            class="event-date"
            href="https://www.facebook.com/events/1000640362322768"
            target="_blank"
            rel="noopener noreferrer"
            ><IconCalendar /> Monday, June 29 at 5:30 &ndash; 9pm</a
          >
        </div>
        <a
          class="event-location"
          href="https://maps.app.goo.gl/bE9THdo92AbrKKeJ7"
          target="_blank"
          rel="noopener noreferrer"
        >
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

        <p>
          Light refreshments will be available, prepared by
          <a
            href="https://www.facebook.com/foodnotbombs.mankato"
            target="_blank"
            rel="noopener noreferrer"
            >Food Not Bombs</a
          >
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
          stable snack items and travel hygiene items to support the group's mutual aide efforts.
          <a
            href="http://facebook.com/photo?fbid=122114030805347036&set=gm.1006781185042019&idorvanity=1000640362322768"
            target="_blank"
            rel="noopener noreferrer"
            >A list of needed items is available here</a
          >.
        </p>
      </div>
    </div>
  </section>
</template>
