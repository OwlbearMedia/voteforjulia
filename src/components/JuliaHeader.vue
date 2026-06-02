<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { faInstagram, faFacebookF } from "@fortawesome/free-brands-svg-icons";
import juliaLogo from '../assets/julia-hamann-for-mankato-mayor.avif';
import { trackDonateClick } from '../lib/analytics';

defineOptions({
    name: 'JuliaHeader'
});

const { title } = defineProps<{
    title: string;
}>();

const showMenu = ref(false);

function toggleMenu() {
    showMenu.value = !showMenu.value;
}

function closeMenu() {
    showMenu.value = false;
}

function handleDonateClick() {
    trackDonateClick('header', 'Donate');
    closeMenu();
}
</script>

<template>
    <header class="bg-julia-dark-green">
        <div class="container">
            <h1 class="sr-only">{{ title }}</h1>
            <div class="logo-container">
                <a href="/" aria-label="Vote for Julia Home">
                    <img :src="juliaLogo" alt="Julia Hamann for Mankato Mayor" class="logo" width="200" height="90"
                        decoding="async" />
                </a>
            </div>
            <button class="menu-toggle" aria-label="Open menu" :aria-expanded="showMenu" aria-controls="main-menu"
                @click="toggleMenu">
                <span class="hamburger"></span>
            </button>

            <nav aria-label="Main navigation">
                <ul class="menu-list" :class="{ open: showMenu }" id="main-menu">
                    <li><RouterLink to="/" @click="closeMenu">Home</RouterLink></li>
                    <li><RouterLink to="/meet-julia" @click="closeMenu">Meet Julia</RouterLink></li>
                    <li><RouterLink :to="{ path: '/', hash: '#issues' }" @click="closeMenu">Issues</RouterLink></li>
                    <li><RouterLink to="/volunteer" @click="closeMenu">Volunteer</RouterLink></li>
                    <li><RouterLink to="/donate" class="donate" @click="handleDonateClick">Donate</RouterLink></li>
                    <li class="social-icons">
                        <a href="https://www.instagram.com/voteforjuliahamann" aria-label="Julia on Instagram"
                            target="_blank" rel="noopener noreferrer"><FontAwesomeIcon :icon="faInstagram" /></a>
                        <a href="https://www.facebook.com/profile.php?id=61590411090366" aria-label="Julia on Facebook"
                            target="_blank" rel="noopener noreferrer"><FontAwesomeIcon :icon="faFacebookF" /></a>
                    </li>
                </ul>
            </nav>
        </div>
    </header>
</template>
