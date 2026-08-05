import { mount, RouterLinkStub, type VueWrapper } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';
import JuliaButton from '../../src/components/JuliaButton.vue';

const global = { stubs: { RouterLink: RouterLinkStub } };

// The focus test is the only one that has to attach to document.body, and
// leaked *markup* is not the reason it gets torn down — vitest.setup.ts already
// clears document.body after every test, which also resets activeElement.
// What that global hook cannot do is run Vue's unmount lifecycle: it strips the
// nodes and leaves the component instance behind. JuliaButton has no teardown
// to run today, so this is hygiene rather than a fix, and it matches how the
// footer and modal specs (whose components do hold listeners and observers)
// already clean up. Registering the wrapper here rather than calling unmount()
// at the end of the test body means it still happens if an assertion throws.
const attached: VueWrapper[] = [];

function mountAttached(options: Parameters<typeof mount>[1] = {}) {
  const wrapper = mount(JuliaButton, { ...options, attachTo: document.body });
  attached.push(wrapper);
  return wrapper;
}

afterEach(() => {
  while (attached.length > 0) {
    attached.pop()?.unmount();
  }
});

describe('JuliaButton', () => {
  it('renders a real <button> with an explicit type by default', () => {
    const wrapper = mount(JuliaButton, { slots: { default: 'Send Message' } });

    expect(wrapper.element.tagName).toBe('BUTTON');
    // Without this a button inside a <form> defaults to type="submit" and
    // silently posts the form.
    expect(wrapper.attributes('type')).toBe('button');
    expect(wrapper.text()).toBe('Send Message');
  });

  it('renders a RouterLink for `to` and an <a> for `href`, with no stray type attribute', () => {
    const routed = mount(JuliaButton, { props: { to: '/donate' }, global });
    expect(routed.findComponent(RouterLinkStub).props('to')).toBe('/donate');
    expect(routed.attributes('type')).toBeUndefined();

    const external = mount(JuliaButton, { props: { href: 'https://example.com' } });
    expect(external.element.tagName).toBe('A');
    expect(external.attributes('href')).toBe('https://example.com');
    expect(external.attributes('type')).toBeUndefined();
  });

  it('applies the colours for each variant', () => {
    const classesFor = (variant: 'primary' | 'secondary' | 'danger') =>
      mount(JuliaButton, { props: { variant } }).classes();

    expect(classesFor('primary')).toEqual(expect.arrayContaining(['bg-leaf', 'text-white']));
    expect(classesFor('secondary')).toEqual(expect.arrayContaining(['bg-white', 'text-fern']));
    expect(classesFor('danger')).toEqual(expect.arrayContaining(['bg-error', 'text-white']));
  });

  // The two-tone ring is the site's only custom focus indicator. Deleting it
  // silently falls back to the UA default, which disappears against at least
  // one of the four backgrounds these buttons sit on.
  it('carries a focus-visible indicator', () => {
    const classes = mount(JuliaButton).classes();

    expect(classes).toEqual(
      expect.arrayContaining([
        'focus-visible:ring-4',
        'focus-visible:ring-ink/60',
        'focus-visible:outline-2',
        'focus-visible:outline-offset-2',
        'focus-visible:outline-white'
      ])
    );
  });

  // Callers pass layout and font-size classes through the fallthrough attr, so
  // they have to land alongside the variant's classes rather than replace them.
  it('merges a caller-supplied class with its own', () => {
    const wrapper = mount(JuliaButton, { attrs: { class: 'w-full text-sm' } });

    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['w-full', 'text-sm', 'bg-leaf', 'rounded-pill'])
    );
  });

  it('forwards listeners and the disabled attribute to the underlying button', async () => {
    const wrapper = mount(JuliaButton, { props: { disabled: true } });

    expect(wrapper.attributes('disabled')).toBeDefined();

    const clickable = mount(JuliaButton);
    await clickable.trigger('click');
    expect(clickable.emitted('click')).toHaveLength(1);
  });

  // Both forms disable their submit button while the request is in flight. The
  // tag swap that handles disabled links must not demote that to type="button",
  // or the form would stop submitting the moment it was re-enabled.
  it('keeps type="submit" on a disabled submit button', () => {
    const wrapper = mount(JuliaButton, { props: { type: 'submit', disabled: true } });

    expect(wrapper.element.tagName).toBe('BUTTON');
    expect(wrapper.attributes('type')).toBe('submit');
    expect(wrapper.attributes('disabled')).toBeDefined();
  });

  // `disabled` is meaningless on an anchor — the attribute does not exist
  // there — so a disabled link renders as a disabled <button> instead. Styling
  // alone was not enough: pointer-events-none only stops the mouse and
  // tabindex="-1" only stops tabbing, leaving element.click() (scripts, and
  // some assistive-tech activation paths) free to navigate and to run the
  // caller's handler.
  it('renders a disabled link as a disabled button, with no href to follow', () => {
    const onClick = vi.fn();
    const wrapper = mountAttached({
      props: { href: '/donate', disabled: true },
      attrs: { onClick }
    });

    expect(wrapper.element.tagName).toBe('BUTTON');
    expect(wrapper.attributes('href')).toBeUndefined();
    expect(wrapper.attributes('disabled')).toBeDefined();

    // The platform refuses to dispatch a click on a disabled form control, so
    // the activation path that defeated the styling-only version is closed.
    (wrapper.element as HTMLElement).click();
    expect(onClick).not.toHaveBeenCalled();
  });

  it('still renders a live link when it is not disabled', () => {
    const wrapper = mount(JuliaButton, { props: { href: '/donate' } });

    expect(wrapper.element.tagName).toBe('A');
    expect(wrapper.attributes('href')).toBe('/donate');
    expect(wrapper.attributes('disabled')).toBeUndefined();
  });

  // JuliaModal focuses its confirm button on open through this method; a
  // template ref alone would hand it a component instance, not an element.
  it('exposes focus() that reaches the rendered element in both forms', () => {
    const asButton = mountAttached();
    asButton.vm.focus();
    expect(document.activeElement).toBe(asButton.element);

    const asLink = mountAttached({ props: { href: '#somewhere' } });
    asLink.vm.focus();
    expect(document.activeElement).toBe(asLink.element);
  });

  // The case above only covers the branch where the root is already an element.
  // With `to` the root is a RouterLink instance and focus() has to go through
  // $el, which is the branch that comment exists for.
  //
  // A real router, not RouterLinkStub: the stub renders an anchor with no href,
  // and an anchor without one is not focusable — so a stubbed version of this
  // test fails while the component is working correctly.
  it('exposes focus() on a routed button, through the component instance', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/donate', component: { template: '<div />' } }
      ]
    });
    await router.push('/');
    await router.isReady();

    const wrapper = mountAttached({ props: { to: '/donate' }, global: { plugins: [router] } });

    expect(wrapper.element.tagName).toBe('A');
    expect(wrapper.attributes('href')).toBe('/donate');

    wrapper.vm.focus();
    expect(document.activeElement).toBe(wrapper.element);
  });
});
