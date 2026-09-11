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
  /** First card only: it is above the fold at every width. Its md+ row-mate stays
   *  lazy so it does not compete with the header logo, the LCP (docs/performance.md). */
  eager?: boolean;
}

interface NewsItem {
  headline: string;
  /** Publication, used for the byline and the JSON-LD publisher. */
  outlet: string;
  /** One entry per person — each becomes its own schema.org `author` Person. */
  authors?: string[];
  /** ISO date, Mankato-local — not the UTC date some outlets put in the URL.
   *  Drives both the schema node and the rendered date. */
  published: string;
  url: string;
  linkLabel: string;
  body: string[];
  image?: NewsImage;
}

/** Newest first — the page renders them in this order. */
const newsItems: NewsItem[] = [
  {
    headline: 'Mankato precinct results mirror primary results',
    outlet: 'Mankato Free Press',
    authors: ['Ethan Becker'],
    published: '2026-08-19',
    url: 'https://www.mankatofreepress.com/news/local_news/mankato-precinct-results-mirror-primary-results/article_51888182-16d7-44d9-8810-42d4997e9418.html',
    linkLabel: 'Read the full article at Mankato Free Press',
    body: [
      'Julia prevails in the primary election. “Incumbent Najwa Massad would end up getting just 114 more votes than the runner-up in the race, Julia Hamann, with Massad receiving 2,378 votes to Hamann’s 2,264. The two will advance to the general election in November…Despite the vote totals, Hamann was actually able to secure more precincts than Massad, winning in 10 of Mankato’s 17 precincts compared to Massad’s seven.”'
    ],
    image: {
      src: '/primary-win.jpg',
      alt: 'Julia Hamann wins primary for Mankato Mayor',
      width: 1009,
      height: 1412,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1009],
      eager: true
    }
  },
  {
    headline: 'Mankato mayor candidates address questions ahead of primary election',
    outlet: 'Mankato Free Press',
    authors: ['Ethan Becker'],
    published: '2026-08-07',
    url: 'https://www.mankatofreepress.com/news/local_news/mankato-mayor-candidates-address-questions-ahead-of-primary-election/article_7d757752-b589-4311-892b-646cd708193a.html',
    linkLabel: 'Read the full article at Mankato Free Press',
    body: [
      'With just days to go before the primary election, The Free Press sent each candidate — Mankato Mayor Najwa Massad, Toby Leonard and Julia Hamann — the same list of questions via email. The following are their responses.'
    ],
    image: {
      src: '/questions.jpg',
      alt: 'Julia Hamann addresses questions ahead of primary election',
      width: 2048,
      height: 1536,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1664]
    }
  },
  {
    headline: 'Julia Hamann and Jacob Bases on running together in Mankato | Get Election Ready',
    outlet: 'The Woven Record',
    authors: ['Mike Lagerquist', 'Becki True'],
    published: '2026-08-06',
    url: 'https://youtu.be/h-v45bBwLtM?si=gu2ppF80kg-aVN7q',
    linkLabel: 'Watch the video on YouTube',
    body: [
      'Julia Hamann and Jacob Bases sit down with Mike and Becki, hosts of the Woven Record, to share about their motivations for running and their goals as progressive candidates.'
    ],
    image: {
      src: '/woven-record.jpg',
      alt: 'Julia and Jacob on the Woven Record',
      width: 1000,
      height: 522,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1000]
    }
  },
  {
    headline: 'Candidate for Mankato Mayor Hosts Campaign Launch Party',
    outlet: 'KEYC',
    authors: ['Kate Jones'],
    published: '2026-06-29',
    url: 'https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/',
    linkLabel: 'Read the full article at KEYC',
    body: [
      'Julia hosts a campaign launch party at Mankato Makerspace. Over 100 people were in attendance to connect, hear speeches, and make their own campaign swag.'
    ],
    image: {
      src: '/launch-party-crowd.jpg',
      alt: 'Julia Hamann for Mankato Mayor launch party',
      width: 2048,
      height: 1360,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1664]
    }
  },
  {
    headline: 'RACE TO WATCH: Julia Hamann',
    outlet: 'Mankato Free Press',
    authors: ['Ethan Becker'],
    published: '2026-06-25',
    url: 'https://www.youtube.com/watch?v=UnVrel_BRfs',
    linkLabel: 'Watch the video on YouTube',
    body: [
      'Julia sits down with Ethan Becker for a recorded interview regarding her motivations for running, her background, and her perspective on issues.'
    ],
    image: {
      src: '/race-to-watch.jpeg',
      alt: 'Julia Hamann interviewed by the Mankato Free Press',
      width: 1000,
      height: 522,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1000]
    }
  },
  {
    headline: 'Hamann, Bases look to bring new conversations to Mankato leadership',
    outlet: 'Mankato Free Press',
    authors: ['Ethan Becker'],
    published: '2026-05-30',
    url: 'https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html',
    linkLabel: 'Read the full article at Mankato Free Press',
    body: [
      'Julia files her affidavit of candidacy for Mayor, alongside Jacob Bases running for city council Ward 3. The two wish to bring new conversations to the city council centered in progressive values.'
    ],
    image: {
      src: '/new-conversation.jpg',
      alt: 'Julia Hamann files her affidavit of candidacy for Mayor of Mankato',
      width: 1101,
      height: 1442,
      imageBreakpoints: [320, 390, 430, 520, 640, 780, 832, 1101]
    }
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

const authorList = new Intl.ListFormat('en', { style: 'long', type: 'conjunction' });

const aboutJulia = { '@type': 'Person', name: 'Julia Hamann' };

// Derived from the same list the page renders, so a new item cannot appear on
// the page without appearing in the structured data. Linked videos are
// NewsArticles too: `VideoObject` needs the video playable on this page.
const schemaNodes = newsItems.map((item) => ({
  '@type': 'NewsArticle',
  headline: item.headline,
  datePublished: item.published,
  ...(item.authors ? { author: item.authors.map((name) => ({ '@type': 'Person', name })) } : {}),
  publisher: { '@type': 'Organization', name: item.outlet },
  url: item.url,
  about: aboutJulia
}));

useHead(
  buildPageHead({
    path: '/news',
    title: 'News | Julia Hamann for Mankato Mayor',
    description:
      'Read the latest news coverage of Julia Hamann’s campaign for Mayor of Mankato — profiles, interviews, and reporting from KEYC, the Mankato Free Press, and The Woven Record.',
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

    <div class="grid gap-8 md:grid-cols-2">
      <article
        v-for="item in newsItems"
        :key="item.url"
        class="rounded-4xl bg-forest px-8 py-4 text-white shadow-strong"
      >
        <h3 class="text-lime">{{ item.headline }}</h3>
        <a
          class="mb-2 inline-flex items-center gap-1.5 font-accent font-normal text-white"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          ><IconCalendar /> {{ formatPublished(item.published) }} &middot; {{ item.outlet }}</a
        >
        <!-- Must stay visible: the JSON-LD credits these authors, and Google ignores unseen markup. -->
        <p v-if="item.authors" class="mb-2 font-accent text-white">
          By {{ authorList.format(item.authors) }}
        </p>

        <a
          v-if="item.image"
          class="my-4 block"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
        >
          <!-- `sizes` is main's width minus the grid gap and card padding; it moves with either. -->
          <Image
            url-endpoint="https://ik.imagekit.io/voteforjulia"
            :src="item.image.src"
            :alt="item.image.alt"
            class="h-auto w-full rounded-lg"
            sizes="(max-width: 767px) calc(100vw - 6.5rem), (max-width: 960px) calc(50vw - 7rem), 368px"
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
    </div>
  </section>
</template>
