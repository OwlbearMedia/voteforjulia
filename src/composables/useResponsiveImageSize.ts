import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

export interface ImageSizeConfig {
  baseWidth: number;
  baseHeight: number;
}

export function useResponsiveImageSize(config: ImageSizeConfig) {
  const { baseWidth, baseHeight } = config;
  const aspectRatio = baseWidth / baseHeight;

  const viewportWidth = ref(baseWidth);

  function updateViewportWidth() {
    if (globalThis.window === undefined) {
      return;
    }

    viewportWidth.value = globalThis.innerWidth;
  }

  onMounted(() => {
    updateViewportWidth();
    globalThis.addEventListener('resize', updateViewportWidth);
  });

  onBeforeUnmount(() => {
    globalThis.removeEventListener('resize', updateViewportWidth);
  });

  const width = computed(() => {
    const horizontalPadding = viewportWidth.value <= 700 ? 40 : 64;
    return Math.min(baseWidth, Math.max(viewportWidth.value - horizontalPadding, 1));
  });

  const height = computed(() => Math.round(width.value / aspectRatio));

  return {
    width,
    height
  };
}
