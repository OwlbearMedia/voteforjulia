<script setup lang="ts">
import { useHead } from '@unhead/vue'
import JuliaMaybeIdk from '../assets/julia-maybe-idk.webp';
import Julia from '../assets/julia.avif';

defineOptions({
    name: 'JuliaAbout'
});

useHead({
    title: 'Meet Julia | Julia Hamann for Mankato Mayor',
    link: [{
        rel: 'canonical',
        href: 'https://voteforjulia.com/meet-julia.html'
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
        content: 'Meet Julia Hamann, lifelong Mankato resident and mayoral candidate. Learn her background, values, and vision for a more just, community-led city.'
    }, {
        name: 'robots',
        content: 'index,follow'
    }, {
        name: 'keywords',
        content: 'Julia Hamann, Mankato Mayor, About Julia, Meet Julia, Julia Hamann background, Julia Hamann values, Julia Hamann vision, Mankato politics, local leadership'
    }, {
        property: 'og:type',
        content: 'website'
    }, {
        property: 'og:site_name',
        content: 'Vote for Julia'
    }, {
        property: 'og:title',
        content: 'Meet Julia | Julia Hamann for Mankato Mayor'
    }, {
        property: 'og:description',
        content: 'Learn about Julia Hamann and her campaign for Mayor of Mankato with a vision for equity, transparency, sustainability, and community-led safety.'
    }, {
        property: 'og:url',
        content: 'https://voteforjulia.com/meet-julia.html'
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
        content: 'Meet Julia | Julia Hamann for Mankato Mayor'
    }, {
        name: 'twitter:description',
        content: 'Learn about Julia Hamann and her campaign for Mayor of Mankato with a vision for equity, transparency, sustainability, and community-led safety.'
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
    <section id="meet-julia">
        <h2>Who is Julia?</h2>
        <p>
            Julia is a proud Mankato “townie” through and through. As a lifelong
            Mankato resident, Julia is committed to giving back to the community
            that has nurtured her.
        </p>
        <p>
            Julia is running for Mayor to change the conversation at City Council
            - to center the conversation around the real-life experiences of
            people in our town. As a social worker, renter, queer woman, survivor
            of gender-based violence, millennial, and auntie, she understands the
            challenges many people in Mankato face and believes everyone should be
            heard and respected - especially those too often left out of decision
            making.
        </p>

        <h3>Early Life</h3>

        <div class="stances-layout">
            <div class="stances-text">
                <p>
                    Julia’s sense of justice and passion for helping others was
                    instilled in her from childhood. Her mom was a career public
                    defender and her dad, a jack of all trades, always helped his
                    neighbors and gave back to his community. Julia’s first volunteer
                    experience was at age nine helping her dad serve meals to unhoused
                    people from a food truck. She knew then that her life would be
                    about making a difference in the lives of others and working for
                    what’s right.
                </p>
                <p>
                    In 2016, Julia earned a Bachelor’s Degree in Social Work from MSU,
                    Mankato where she was an Honors student and Presidential Scholar.
                    Julia has worked in the social services field for 10+ years, and
                    early on spent a year as an AmeriCorps Volunteer. In her career,
                    Julia has worked with adults with disabilities, children and
                    youth, those struggling with substance addiction, and victims of
                    domestic and sexual violence. She is currently a programming
                    director in the anti-violence field. Outside of work, Julia
                    volunteers with nonprofits, attends local community events, and is
                    active in mutual aid networks. Julia consistently shows up for her
                    community, and will continue to show up for the people of this
                    community as Mayor of Mankato.
                </p>
            </div>
            <img :src="JuliaMaybeIdk" alt="Julia Hamann" class="coming-soon maybe-idk" width="690" height="960"
                loading="lazy" decoding="async" />
        </div>

        <h3>Core Values</h3>
        <p>
            Julia’s guiding values include equity, accountability, transparency,
            dignity, justice, freedom, growth, and community.
        </p>
        <p>
            Julia is a nurturer, helper, thinker, and activator. She thinks and
            feels deeply, and knows when to take action and make things happen,
            especially for the betterment of this community.
        </p>

        <h3>Inspiration for Running for Mayor</h3>
        <p>
            Julia has always been committed to making a positive impact in her
            community, guided by a belief in the interconnectedness of all life
            instilling a moral responsibility to care for others. The current
            political landscape has deepened her understanding of the influence
            local politics holds in shaping everyday life, prompting her to take a
            closer look at Mankato city governance.
        </p>
        <p>
            As Julia became more engaged in politics in Mankato, she was
            encouraged by some of the city’s goals but disappointed by responses
            to issues she deeply cared about. She felt her progressive values were
            not fully represented.
        </p>
        <p>
            Julia wants our town to have conversations about important topics and
            be part of building creative solutions to the issues facing our
            community today. She is ready for the city to act boldly, be willing
            to try new things, and incorporate diverse perspectives. She
            understands the importance of local policy making and believes that
            everyday citizens can make a big impact.
        </p>

        <div class="stances-layout">
            <img :src="Julia" alt="Julia Hamann" class="coming-soon" width="690" height="960" loading="lazy"
                decoding="async" />
            <div class="stances-text stances-text-centered">
                <blockquote>
                    "I’ve heard a lot about what’s NOT possible and I’m ready to start
                    a new conversation."<br />
                    - Julia
                </blockquote>
                <p>
                    If you’re ready for CHANGE and for our city to start some new
                    conversations, vote for Julia!
                </p>
            </div>
        </div>
    </section>
</template>