import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue';

export interface ImageSizeConfig {
  baseWidth: number;
  baseHeight: number;
  target?: Ref<HTMLElement | null>;
}

function getBrowserWindow() {
  if (globalThis.window === undefined) {
    return undefined;
  }

  return globalThis.window;
}

export function useResponsiveImageSize(config: ImageSizeConfig) {
  const { baseWidth, baseHeight, target } = config;
  const aspectRatio = baseWidth / baseHeight;

  function getViewportWidth() {
    const browserWindow = getBrowserWindow();
    if (!browserWindow) {
      return baseWidth;
    }

    return Math.round(browserWindow.visualViewport?.width ?? browserWindow.innerWidth);
  }

  const measuredWidth = ref(getViewportWidth());
  let resizeObserver: ResizeObserver | null = null;

  function updateMeasuredWidth() {
    if (!getBrowserWindow()) {
      return;
    }

    if (target?.value) {
      const nextWidth = Math.round(target.value.getBoundingClientRect().width);
      if (nextWidth > 0) {
        measuredWidth.value = nextWidth;
      }
      return;
    }

    measuredWidth.value = getViewportWidth();
  }

  function attachResizeObserver() {
    if (!getBrowserWindow()) {
      return;
    }

    resizeObserver?.disconnect();
    resizeObserver = null;

    if (!target?.value || typeof ResizeObserver === 'undefined') {
      return;
    }

    resizeObserver = new ResizeObserver(() => {
      updateMeasuredWidth();
    });
    resizeObserver.observe(target.value);
  }

  onMounted(() => {
    const browserWindow = getBrowserWindow();
    updateMeasuredWidth();
    attachResizeObserver();

    if (!target && browserWindow) {
      browserWindow.addEventListener('resize', updateMeasuredWidth);
      globalThis.addEventListener('orientationchange', updateMeasuredWidth);
      browserWindow.visualViewport?.addEventListener('resize', updateMeasuredWidth);
    }
  });

  watch(
    () => target?.value,
    () => {
      updateMeasuredWidth();
      attachResizeObserver();
    }
  );

  onBeforeUnmount(() => {
    const browserWindow = getBrowserWindow();
    if (!browserWindow) {
      return;
    }

    resizeObserver?.disconnect();
    resizeObserver = null;

    browserWindow.removeEventListener('resize', updateMeasuredWidth);
    globalThis.removeEventListener('orientationchange', updateMeasuredWidth);
    browserWindow.visualViewport?.removeEventListener('resize', updateMeasuredWidth);
  });

  const width = computed(() => {
    const viewportPadding = measuredWidth.value <= 700 ? 40 : 64;
    const viewportBasedWidth = measuredWidth.value - viewportPadding;
    const widthBudget = target ? measuredWidth.value : viewportBasedWidth;

    return Math.max(widthBudget, 1);
  });

  const height = computed(() => Math.round(width.value / aspectRatio));

  return {
    width,
    height
  };
}
