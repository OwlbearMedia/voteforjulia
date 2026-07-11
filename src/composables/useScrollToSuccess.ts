import { nextTick, ref, watch, type Ref } from 'vue';

/**
 * View-only concern: scrolls the success message into view once it renders,
 * accounting for the sticky header height, and focuses it for accessibility.
 * The template ref itself is created by the caller via `useTemplateRef` so
 * Vue's compiler can still statically bind it to the `ref="..."` in the
 * template.
 */
export function useScrollToSuccess(
  successMessageRef: Readonly<Ref<HTMLElement | null>>,
  isSubmitted: Ref<boolean>
): void {
  const hasScrolledToSuccess = ref(false);

  async function scrollToSuccessMessage(): Promise<void> {
    await nextTick();

    const successElement = successMessageRef.value;
    if (!successElement || hasScrolledToSuccess.value) {
      return;
    }

    const headerElement = document.querySelector('header');
    const headerHeight =
      headerElement instanceof HTMLElement ? headerElement.getBoundingClientRect().height : 0;
    const targetTop = successElement.getBoundingClientRect().top + window.scrollY;
    const scrollTop = Math.max(targetTop - headerHeight - 8, 0);

    window.scrollTo({ top: scrollTop, behavior: 'smooth' });
    successElement.focus();
    hasScrolledToSuccess.value = true;
  }

  watch(isSubmitted, (submitted) => {
    if (!submitted) {
      hasScrolledToSuccess.value = false;
      return;
    }

    void scrollToSuccessMessage();
  });

  watch(successMessageRef, (element) => {
    if (!element || !isSubmitted.value) {
      return;
    }

    void scrollToSuccessMessage();
  });
}
