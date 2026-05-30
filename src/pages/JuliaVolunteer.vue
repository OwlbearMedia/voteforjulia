<script setup lang="ts">
import { useHead } from '@unhead/vue'
import Julia from '../assets/julia.avif';
import JuliaContactForm from '../components/JuliaContactForm.vue';

defineOptions({
    name: 'JuliaVolunteer'
});

useHead({
    title: 'Volunteer | Julia Hamann for Mankato Mayor',
    link: [{
        rel: 'canonical',
        href: 'https://voteforjulia.com/volunteer.html'
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
        content: 'Volunteer for the Julia Hamann campaign to help build a more just, community-led Mankato.'
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
        content: 'Volunteer | Julia Hamann for Mankato Mayor'
    }, {
        property: 'og:description',
        content: 'Volunteer for the Julia Hamann campaign to help build a more just, community-led Mankato.'
    }, {
        property: 'og:url',
        content: 'https://voteforjulia.com/volunteer.html'
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
        content: 'Volunteer | Julia Hamann for Mankato Mayor'
    }, {
        name: 'twitter:description',
        content: 'Volunteer for the Julia Hamann campaign to help build a more just, community-led Mankato.'
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
    <section id="contact">
        <h2>Volunteer</h2>

        <div class="stances-layout">
            <div class="stances-text">
                <p>
                    Join the campaign team to help with outreach, events, and voter
                    engagement.
                </p>

                <h3>Volunteer for the Campaign</h3>
                <JuliaContactForm />
            </div>
            <img :src="Julia" alt="Julia Hamann for Mankato Mayor" class="coming-soon" width="767" height="960"
                loading="lazy" decoding="async" />
        </div>
    </section>
</template>