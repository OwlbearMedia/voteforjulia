<script setup lang="ts">
import { computed, ref, type ComponentPublicInstance } from 'vue';
import { RouterLink, type RouteLocationRaw } from 'vue-router';

defineOptions({
  name: 'JuliaButton'
});

const props = withDefaults(
  defineProps<{
    /** `primary` is the filled leaf action; `secondary` is the white-on-dark
     *  one. `danger` is primary's destructive form — the modal's confirm
     *  button is the only caller. */
    variant?: 'primary' | 'secondary' | 'danger';
    /** Renders a <RouterLink> for an in-app route… */
    to?: RouteLocationRaw;
    /** …an <a> for an external URL, and a <button> when neither is set. */
    href?: string;
    type?: 'button' | 'submit' | 'reset';
  }>(),
  {
    variant: 'primary',
    to: undefined,
    href: undefined,
    type: 'button'
  }
);

// Tailwind's scanner reads these string literals like any template text — which
// works only because each class appears here whole, never concatenated.
//
// The focus ring is two-tone on purpose. These buttons sit on the light page
// background, the forest footer, the leaf nav dropdown and the mint modal, and
// no single colour clears 3:1 against all four. `ring-4` fills the 0–4px band
// with near-black and the offset outline paints white over its outer half, so
// whichever band the background swallows, the other one shows. `ring` composes
// with `shadow-soft` rather than replacing it — they are separate variables in
// v4's box-shadow chain.
//
// Ordered the way prettier-plugin-tailwindcss orders class attributes. The
// plugin only sorts markup, so a string in script drifts from the house order
// silently; to re-derive it, paste the string into a scratch `class=""` and
// run prettier on it.
const BUTTON_BASE =
  'inline-flex cursor-pointer items-center justify-center gap-2 rounded-pill px-6 pt-3 pb-2 font-action font-semibold shadow-soft hover:no-underline focus-visible:ring-4 focus-visible:ring-ink/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:opacity-60';

const BUTTON_VARIANTS = {
  primary: 'bg-leaf text-white hover:bg-sprout/70',
  // text-fern, not text-leaf: leaf on white is 4.52:1, which clears AA for
  // normal text by a hair. Fern is the same family at 5.47:1 — see the
  // --color-link note in style.css.
  secondary: 'bg-white text-fern hover:bg-mint',
  danger: 'bg-error text-white hover:bg-error/85'
} as const;

// Font size is deliberately not part of the base: the footer/header/home
// buttons run at body size, the modal and form buttons at `text-sm`. Callers
// pass that (and any layout classes) through the fallthrough `class` attr.
const classes = computed(() => [BUTTON_BASE, BUTTON_VARIANTS[props.variant]]);

const tag = computed(() => (props.to ? RouterLink : props.href ? 'a' : 'button'));

// Built rather than spread from props so a <button> never receives a stray
// `to`/`href` and a link never receives `type`.
const tagProps = computed(() => {
  if (props.to) return { to: props.to };
  if (props.href) return { href: props.href };
  return { type: props.type };
});

const root = ref<HTMLElement | ComponentPublicInstance | null>(null);

// A template ref on this component yields the component instance, and the root
// is a RouterLink instance rather than an element when `to` is set — so callers
// that manage focus (JuliaModal focuses its confirm button on open) get a
// `focus()` that works either way instead of reaching for `$el` themselves.
defineExpose({
  focus() {
    const el = root.value instanceof HTMLElement ? root.value : (root.value?.$el as HTMLElement);
    el?.focus();
  }
});
</script>

<template>
  <component :is="tag" ref="root" v-bind="tagProps" :class="classes">
    <slot />
  </component>
</template>
