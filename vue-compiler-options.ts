/**
 * Vue template compiler options shared by the Vite build and the Vitest run.
 *
 * These have to match: when only the build knew about `<dbox-widget>`, the unit
 * tests compiled the Donate page differently from production and could not have
 * caught the tag being dropped from the prerendered HTML.
 */
export const vueCompilerOptions = {
  /** Tags rendered as native custom elements rather than looked up as components. */
  isCustomElement: (tag: string) => tag === 'dbox-widget'
};
