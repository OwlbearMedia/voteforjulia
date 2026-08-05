<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="modal-backdrop">
      <div v-if="open" class="fixed inset-0 z-floating bg-ink/60" aria-hidden="true"></div>
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
            tabindex="-1"
            class="relative w-full max-w-lg overflow-hidden rounded-lg bg-white text-left text-ink shadow-strong outline-none sm:my-8"
            @keydown="onKeydown"
          >
            <header
              class="flex items-center gap-3 border-b border-mist/60 bg-forest px-4 py-4 sm:px-6"
            >
              <div
                v-if="props.variant !== 'default'"
                class="flex size-10 shrink-0 items-center justify-center rounded-full"
                :class="iconClasses"
              >
                <slot name="icon">
                  <IconWarning class="text-2xl" />
                </slot>
              </div>
              <!-- h2, not h3: the only heading above this is the page's
                   visually-hidden h1 in App.vue, and skipping a level fails
                   axe's heading-order. `mt-0` cancels the 3rem top margin the
                   base h2 rule adds for prose; text-event already overrides
                   its font-size. -->
              <h2
                :id="titleId"
                class="mt-0 mb-0 flex-1 pt-1 font-display text-event leading-none text-lime"
              >
                {{ title }}
              </h2>
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
              <!-- Only the destructive variant recolors the confirm button;
                   warning keeps the standard green action. -->
              <JuliaButton
                v-if="confirmLabel"
                ref="confirmButton"
                :variant="props.variant === 'danger' ? 'danger' : 'primary'"
                class="w-full text-sm sm:ml-3 sm:w-auto"
                @click="confirm"
              >
                {{ confirmLabel }}
              </JuliaButton>
              <JuliaButton
                v-if="cancelLabel"
                variant="secondary"
                class="mt-3 w-full text-sm sm:mt-0 sm:w-auto"
                @click="close"
              >
                {{ cancelLabel }}
              </JuliaButton>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue';
import JuliaButton from './JuliaButton.vue';
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

const titleId = useId();
const panel = ref<HTMLElement>();
const confirmButton = ref<InstanceType<typeof JuliaButton>>();

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
  const active = document.activeElement;

  // The panel itself is the starting focus target when there is no confirm
  // button, so shift-tabbing off it has to wrap to the end like `first` does.
  if (event.shiftKey && (active === first || active === panel.value)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    previouslyFocused = document.activeElement as HTMLElement | null;
    lockBodyScroll();
    // The confirm button is optional. Without it, focus the panel instead so
    // the dialog is announced, Escape reaches `onKeydown`, and the tab trap
    // engages — leaving focus on <body> would strand keyboard users behind a
    // backdrop they cannot dismiss.
    nextTick(() => (confirmButton.value ?? panel.value)?.focus());
  } else {
    unlockBodyScroll();
    previouslyFocused?.focus();
    previouslyFocused = null;
  }
});

// Never leave the page locked if the modal unmounts while still open.
onBeforeUnmount(unlockBodyScroll);
</script>
