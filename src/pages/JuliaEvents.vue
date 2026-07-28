<script setup lang="ts">
import { useHead } from '@unhead/vue';
import IconLocation from '../components/icons/IconLocation.vue';
import IconCalendar from '../components/icons/IconCalendar.vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaEvents'
});

useHead(
  buildPageHead({
    path: '/events',
    title: 'Events | Julia Hamann for Mankato Mayor',
    description:
      'Find upcoming events for the Julia Hamann campaign — town halls, canvasses, and community meetups in Mankato.',
    schemaNodes: [
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
      },
      {
        '@type': 'Event',
        name: 'Primary Win Party!',
        description:
          'Celebrate the results of the primary election with candidate Julia Hamann for Mankato Mayor.',
        startDate: '2026-08-14T19:30:00-05:00',
        eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
        eventStatus: 'https://schema.org/EventScheduled',
        url: 'https://www.facebook.com/events/2530643504031415/',
        location: {
          '@type': 'Place',
          name: 'WineCafe Bar',
          address: {
            '@type': 'PostalAddress',
            addressLocality: 'Mankato',
            addressRegion: 'MN',
            addressCountry: 'US'
          }
        },
        organizer: {
          '@type': 'Person',
          name: 'Julia Hamann',
          url: 'https://voteforjulia.com/'
        }
      }
    ]
  })
);
</script>

<template>
  <section id="events">
    <h2>Upcoming Events</h2>

    <p>Check out upcoming events below:</p>

    <div class="bg-forest shadow-strong text-white py-4 px-8 rounded-4xl mb-8">
      <div class="event-heading">
        <h3 class="text-event text-lime">Primary Election Day!</h3>
        <a
          class="text-white inline-flex items-center gap-1.5 font-accent text-xl font-normal mb-2"
          href="https://www.sos.mn.gov/elections-voting/election-day-voting"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> August 11, 2026</a
        >
      </div>

      <hr class="hr-event" />

      <p>
        Check your voter registration:
        <a
          class="text-lime"
          href="https://www.sos.mn.gov/elections-voting/register-to-vote/"
          target="_blank"
          rel="noopener noreferrer"
          >https://www.sos.mn.gov/elections-voting/register-to-vote/</a
        >
      </p>
      <p>
        Find your polling place:
        <a
          class="text-lime"
          href="https://www.sos.mn.gov/elections-voting/election-day-voting"
          target="_blank"
          rel="noopener noreferrer"
          >https://www.sos.mn.gov/elections-voting/election-day-voting</a
        >
      </p>
    </div>

    <div class="bg-forest shadow-strong text-white py-4 px-8 rounded-4xl mb-8">
      <div class="event-heading">
        <h3 class="text-event text-lime">Primary Win Party!</h3>
        <div>
          <a
            class="text-white inline-flex items-center gap-1.5 font-accent text-xl font-normal mb-2"
            href="https://www.facebook.com/events/2530643504031415/"
            target="_blank"
            rel="noopener noreferrer"
            ><IconCalendar /> Friday, August 14 at 7:30pm</a
          >
        </div>
        <a
          class="inline-flex items-center text-lime gap-1.5 font-accent text-xl font-normal"
          href="https://www.facebook.com/events/2530643504031415/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <IconLocation class="w-4 h-4 shrink-0" /> WineCafe Bar</a
        >
      </div>

      <hr class="hr-event" />

      <p>
        I can't predict the outcome of the primary vote for Mankato Mayor, but I am feeling hopeful
        that the results will be in my favor! When that time comes, I'd love to celebrate with my
        supporters so we're throwing another party!
      </p>
      <p>I will give a brief speech around 8pm followed by a DJ set by MisterRodger!</p>
      <p>Come mingle, dance, and celebrate all the hard work we've put into this campaign!</p>
      <p>
        There will be a table with campaign materials and information, but the main focus of this
        event is simply to connect and have some fun!
      </p>
    </div>
  </section>

  <section id="past-events">
    <h2>Past Events</h2>

    <div class="bg-forest shadow-strong text-white py-4 px-8 rounded-4xl mb-8">
      <div class="event-heading">
        <h3 class="text-event text-lime">Campaign Launch Party!</h3>
        <div>
          <a
            class="text-white inline-flex items-center gap-1.5 font-accent text-xl font-normal mb-2"
            href="https://www.facebook.com/events/1000640362322768"
            target="_blank"
            rel="noopener noreferrer"
            ><IconCalendar /> Monday, June 29 at 5:30 &ndash; 9pm</a
          >
        </div>
        <a
          class="inline-flex items-center text-lime gap-1.5 font-accent text-xl font-normal"
          href="https://maps.app.goo.gl/bE9THdo92AbrKKeJ7"
          target="_blank"
          rel="noopener noreferrer"
        >
          <IconLocation class="w-4 h-4 shrink-0" /> Mankato Makerspace, 1700 3rd Ave</a
        >
      </div>

      <hr class="hr-event" />

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
            class="text-lime"
            href="https://www.facebook.com/foodnotbombs.mankato"
            target="_blank"
            rel="noopener noreferrer"
            >Food Not Bombs</a
          >
        </p>

        <dl class="grid grid-cols-[100px_1fr] items-center my-8">
          <dt class="font-semibold text-xl text-lime font-display">5:30PM</dt>
          <dd class="bg-sprout/50 rounded-lg my-2 py-3 px-4 font-accent text-xl font-normal">
            Social hour - Mingle, snack, &amp; craft
          </dd>

          <dt class="font-semibold text-xl text-lime font-display">6:45PM</dt>
          <dd class="bg-sprout/50 rounded-lg my-2 py-3 px-4 font-accent text-xl font-normal">
            Candidate speeches
          </dd>

          <dt class="font-semibold text-xl text-lime font-display">7:00PM</dt>
          <dd class="bg-sprout/50 rounded-lg my-2 py-3 px-4 font-accent text-xl font-normal">
            Music by Ark &amp; Grum
          </dd>

          <dt class="font-semibold text-xl text-lime font-display">8:00PM</dt>
          <dd class="bg-sprout/50 rounded-lg my-2 py-3 px-4 font-accent text-xl font-normal">
            Music by Laura Schultz &amp; Colin Scharf
          </dd>
        </dl>

        <ul class="list-none p-0 my-8">
          <li class="sprout-bullet flex items-start gap-4 mb-3">
            <div>
              <span class="underline">Make your own campaign swag</span><br />
              Screen printing, button making, &amp; block printing
            </div>
          </li>
          <li class="sprout-bullet flex items-start gap-4 mb-3">
            <div>
              <span class="underline">Support the campaign</span><br />
              Donate, volunteer, yard signs, &amp; campaign lit
            </div>
          </li>
        </ul>

        <p>
          <a class="text-lime" href="https://www.facebook.com/foodnotbombs.mankato" target="_blank"
            >Food Not Bombs</a
          >
          will also be collecting in kind donations of tote bags, reusable water bottles, shelf
          stable snack items and travel hygiene items to support the group's mutual aide efforts.
          <a
            class="text-lime"
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
