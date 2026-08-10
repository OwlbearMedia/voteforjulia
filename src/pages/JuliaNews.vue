<script setup lang="ts">
import { Image } from '@imagekit/vue';
import { useHead } from '@unhead/vue';
import IconCalendar from '../components/icons/IconCalendar.vue';
import { buildPageHead } from '../lib/pageHead';

defineOptions({
  name: 'JuliaNews'
});

interface NewsImage {
  src: string;
  alt: string;
  /** Intrinsic size of the source file — reserves the right box against layout shift. */
  width: number;
  height: number;
  imageBreakpoints: number[];
  /** Only the first card is above the fold; everything below it loads lazily. */
  eager?: boolean;
}

interface NewsItem {
  headline: string;
  /** Publication, used for the byline and the JSON-LD publisher. */
  outlet: string;
  /** Reporter's byline where the piece has one; the video interview does not. */
  author?: string;
  /** ISO date — drives both the schema node and the rendered date. */
  published: string;
  url: string;
  linkLabel: string;
  body: string[];
  image?: NewsImage;
  /** Present when the coverage is a video, which makes it a VideoObject rather
   *  than a NewsArticle in the JSON-LD graph. */
  video?: { description: string; thumbnailUrl: string };
}

/** Newest first — the page renders them in this order. */
const newsItems: NewsItem[] = [
  {
    headline: 'Candidate for Mankato Mayor Hosts Campaign Launch Party',
    outlet: 'KEYC',
    author: 'Kate Jones',
    published: '2026-06-29',
    url: 'https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/',
    linkLabel: 'Read the full article at KEYC',
    body: [
      'Julia’s campaign launch party at The Makerspace drew more than 100 attendees for button-making, screen printing, and live music. Guests connected directly with Julia, chipped in donations for Food Not Bombs, and picked up $10 yard signs to show their support ahead of the August 11th primary.'
    ],
    image: {
      src: '/launch-party.jpg',
      alt: 'Julia Hamann for Mankato Mayor launch party',
      width: 2048,
      height: 1365,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1664],
      eager: true
    }
  },
  {
    headline: 'RACE TO WATCH: Julia Hamann',
    outlet: 'Mankato Free Press',
    published: '2026-06-25',
    url: 'https://www.youtube.com/watch?v=UnVrel_BRfs',
    linkLabel: 'Watch the video on YouTube',
    body: [
      'Julia sat down with the Mankato Free Press to discuss her campaign and her stances on the issues that matter most to the city.'
    ],
    image: {
      src: '/race-to-watch.jpeg',
      alt: 'Julia Hamann interviewed by the Mankato Free Press',
      width: 1000,
      height: 522,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1000]
    },
    video: {
      description:
        'We sat down with candidate for Mankato mayor Julia Hamann to discuss her campaign and her stances on important issues to the city.',
      thumbnailUrl: 'https://i.ytimg.com/vi/UnVrel_BRfs/hqdefault.jpg'
    }
  },
  {
    headline: 'RACE TO WATCH: Hamann hopes to bring conversation to City Council',
    outlet: 'Mankato Free Press',
    author: 'Ethan Becker',
    published: '2026-06-08',
    url: 'https://www.mankatofreepress.com/news/local_news/race-to-watch-hamann-hopes-to-bring-conversation-to-city-council/article_167d04f5-3f33-4b85-a921-8e6e72a43b16.html',
    linkLabel: 'Read the full article at Mankato Free Press',
    body: [
      'In this “Race to Watch” profile, the Mankato Free Press explored Julia’s approach heading into the primary against incumbent Najwa Massad and challenger Toby Leonard. Rather than leading with a fixed policy platform, Julia emphasized bringing more community conversation into City Council decisions — including participatory budgeting, stronger tenant protections, and a careful look at data center development.'
    ]
  },
  {
    headline: 'Mankato candidates officially file for office, with passing of Tuesday deadline',
    outlet: 'KEYC',
    author: 'Aaron Stuve',
    published: '2026-06-03',
    url: 'https://www.keyc.com/2026/06/03/mankato-candidates-file-office/',
    linkLabel: 'Read the full article at KEYC',
    body: [
      'Tuesday marked the filing deadline for Minnesota candidates across local, state, and federal races. In Mankato’s mayoral contest, incumbent Mayor Najwa Massad is seeking her third term, facing challengers Toby Leonard and Julia, who is making a push through a grassroots campaign. An August primary will narrow the mayoral field to two candidates before the November general election.'
    ]
  },
  {
    headline: 'Hamann, Bases look to bring new conversations to Mankato leadership',
    outlet: 'Mankato Free Press',
    author: 'Ethan Becker',
    published: '2026-05-30',
    url: 'https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html',
    linkLabel: 'Read the full article at Mankato Free Press',
    body: [
      'This profile looks at Julia, 33, and Jacob Bases, 37, who is running for the Ward 3 City Council seat — both of whom would be among the youngest members of Mankato’s leadership if elected. Julia discussed how her age and background in social services shape her perspective on rental equity, public safety reform, and environmental justice.'
    ]
  }
];

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December'
];

/**
 * `2026-06-29` -> `June 29, 2026`, without going through `Date`.
 *
 * `new Date('2026-06-29')` parses as UTC midnight, so any formatter running in
 * a US timezone renders it as the 28th — and prerendering would bake that
 * off-by-one date into the static HTML.
 */
function formatPublished(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);

  return `${MONTH_NAMES[month - 1]} ${day}, ${year}`;
}

const aboutJulia = { '@type': 'Person', name: 'Julia Hamann' };

// Derived from the same list the page renders, so a new item cannot appear on
// the page without appearing in the structured data.
const schemaNodes = newsItems.map((item) =>
  item.video
    ? {
        '@type': 'VideoObject',
        name: item.headline,
        uploadDate: item.published,
        description: item.video.description,
        thumbnailUrl: item.video.thumbnailUrl,
        publisher: { '@type': 'Organization', name: item.outlet },
        url: item.url,
        about: aboutJulia
      }
    : {
        '@type': 'NewsArticle',
        headline: item.headline,
        datePublished: item.published,
        ...(item.author ? { author: { '@type': 'Person', name: item.author } } : {}),
        publisher: { '@type': 'Organization', name: item.outlet },
        url: item.url,
        about: aboutJulia
      }
);

useHead(
  buildPageHead({
    path: '/news',
    title: 'News | Julia Hamann for Mankato Mayor',
    description:
      'Read the latest news coverage of Julia Hamann’s campaign for Mayor of Mankato — profiles, interviews, and reporting from KEYC and the Mankato Free Press.',
    socialDescription:
      'Read the latest news coverage of Julia Hamann’s campaign for Mankato Mayor.',
    schemaNodes
  })
);
</script>

<template>
  <section id="news">
    <h2>Julia in the news</h2>

    <p>Check out the latest coverage of Julia’s campaign:</p>

    <article
      v-for="item in newsItems"
      :key="item.url"
      class="mb-8 rounded-4xl bg-forest px-8 py-4 text-white shadow-strong"
    >
      <h3 class="text-event text-lime">{{ item.headline }}</h3>
      <a
        class="mb-2 inline-flex items-center gap-1.5 font-accent text-xl font-normal text-white"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
        ><IconCalendar /> {{ formatPublished(item.published) }} &middot; {{ item.outlet }}</a
      >

      <hr class="hr-event" />

      <a
        v-if="item.image"
        class="my-4 block"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Image
          url-endpoint="https://ik.imagekit.io/voteforjulia"
          :src="item.image.src"
          :alt="item.image.alt"
          class="h-auto w-full rounded-lg"
          sizes="(max-width: 767px) calc(100vw - 6.5rem), (max-width: 960px) calc(100vw - 8rem), 832px"
          :image-breakpoints="item.image.imageBreakpoints"
          :device-breakpoints="[]"
          :width="item.image.width"
          :height="item.image.height"
          crossorigin="anonymous"
          :fetchpriority="item.image.eager ? 'high' : undefined"
          :loading="item.image.eager ? 'eager' : 'lazy'"
          :decoding="item.image.eager ? undefined : 'async'"
        />
      </a>

      <p v-for="(paragraph, index) in item.body" :key="index">{{ paragraph }}</p>

      <p>
        <a class="text-lime" :href="item.url" target="_blank" rel="noopener noreferrer">{{
          item.linkLabel
        }}</a>
      </p>
    </article>
  </section>
</template>
