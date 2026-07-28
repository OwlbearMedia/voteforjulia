<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="modal-backdrop">
      <div v-if="open" class="fixed inset-0 bg-ink/60 z-floating" aria-hidden="true"></div>
    </Transition>

    <!-- Panel -->
    <Transition name="modal-panel">
      <div
        v-if="open"
        class="fixed inset-0 z-floating overflow-y-auto overscroll-contain"
        @click.self="close"
      >
        <div
          class="flex min-h-full items-center justify-center p-4 text-center sm:p-0"
          @click.self="close"
        >
          <div
            ref="panel"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="titleId"
            class="relative w-full max-w-lg overflow-hidden rounded-lg bg-white text-left text-ink shadow-strong sm:my-8"
            @keydown="onKeydown"
          >
            <header
              class="flex bg-forest items-center gap-3 border-b border-mist/60 px-4 py-4 sm:px-6"
            >
              <div
                class="flex size-10 shrink-0 items-center justify-center rounded-full"
                :class="iconClasses"
              >
                <slot name="icon">
                  <IconWarning class="text-2xl" />
                </slot>
              </div>
              <h3
                :id="titleId"
                class="mb-0 flex-1 pt-1 text-event leading-none font-display text-lime"
              >
                {{ title }}
              </h3>
              <button
                type="button"
                aria-label="Close"
                class="shrink-0 cursor-pointer text-xl text-white hover:text-lime"
                @click="close"
              >
                <IconXmark />
              </button>
            </header>
            <div class="bg-mint/60 px-4 py-4 text-ink/80 sm:px-6">
              <slot />
            </div>
            <div class="bg-mint/60 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
              <button
                v-if="confirmLabel"
                ref="confirmButton"
                type="button"
                class="inline-flex w-full justify-center rounded-pill pt-3 pb-2 px-6 font-action font-semibold text-sm text-white shadow-soft cursor-pointer sm:ml-3 sm:w-auto"
                :class="confirmClasses"
                @click="confirm"
              >
                {{ confirmLabel }}
              </button>
              <button
                v-if="cancelLabel"
                type="button"
                class="mt-3 inline-flex w-full justify-center rounded-pill pt-3 pb-2 px-6 font-action font-semibold text-sm text-forest bg-white shadow-soft cursor-pointer hover:bg-mint sm:mt-0 sm:w-auto"
                @click="close"
              >
                {{ cancelLabel }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue';
import IconWarning from './icons/IconWarning.vue';
import IconXmark from './icons/IconXmark.vue';

const open = defineModel<boolean>('open', { default: false });

const props = withDefaults(
  defineProps<{
    title: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: 'default' | 'danger' | 'warning';
  }>(),
  {
    confirmLabel: '',
    cancelLabel: 'Cancel',
    variant: 'default'
  }
);

const emit = defineEmits<{ confirm: []; cancel: [] }>();

// Full class strings so Tailwind's scanner picks them up (no concatenation).
const iconClasses = computed(
  () =>
    ({
      default: 'bg-sprout/25 text-forest',
      danger: 'bg-error/10 text-error',
      warning: 'bg-warning/15 text-warning'
    })[props.variant]
);

// Only the destructive variant recolors the confirm button; warning keeps the
// standard green action.
const confirmClasses = computed(() =>
  props.variant === 'danger' ? 'bg-error hover:bg-error/85' : 'bg-leaf hover:bg-sprout/70'
);

const titleId = useId();
const panel = ref<HTMLElement>();
const confirmButton = ref<HTMLButtonElement>();

// Remember what was focused before opening so we can restore it on close.
let previouslyFocused: HTMLElement | null = null;

// Lock page scroll while open. `overflow: hidden` alone doesn't stop iOS touch
// scrolling, so pin the body with `position: fixed` (offset by the current
// scroll) and restore the scroll position on unlock.
let lockedScrollY = 0;

function lockBodyScroll() {
  lockedScrollY = window.scrollY;
  const { body } = document;
  body.style.position = 'fixed';
  body.style.top = `-${lockedScrollY}px`;
  body.style.left = '0';
  body.style.right = '0';
  body.style.overflow = 'hidden';
}

function unlockBodyScroll() {
  const { body } = document;
  if (body.style.position !== 'fixed') return;
  body.style.position = '';
  body.style.top = '';
  body.style.left = '';
  body.style.right = '';
  body.style.overflow = '';
  window.scrollTo(0, lockedScrollY);
}

function close() {
  open.value = false;
  emit('cancel');
}

function confirm() {
  open.value = false;
  emit('confirm');
}

// Escape to close; Tab wraps focus within the panel (lightweight focus trap).
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault();
    close();
    return;
  }
  if (event.key !== 'Tab' || !panel.value) return;

  const focusable = panel.value.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    previouslyFocused = document.activeElement as HTMLElement | null;
    lockBodyScroll();
    nextTick(() => confirmButton.value?.focus());
  } else {
    unlockBodyScroll();
    previouslyFocused?.focus();
    previouslyFocused = null;
  }
});

// Never leave the page locked if the modal unmounts while still open.
onBeforeUnmount(unlockBodyScroll);
</script>
