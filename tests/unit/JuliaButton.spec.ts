import { mount, RouterLinkStub } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import JuliaButton from '../../src/components/JuliaButton.vue';

const global = { stubs: { RouterLink: RouterLinkStub } };

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
    const wrapper = mount(JuliaButton, { attrs: { disabled: true } });

    expect(wrapper.attributes('disabled')).toBeDefined();

    const clickable = mount(JuliaButton);
    await clickable.trigger('click');
    expect(clickable.emitted('click')).toHaveLength(1);
  });

  // JuliaModal focuses its confirm button on open through this method; a
  // template ref alone would hand it a component instance, not an element.
  it('exposes focus() that reaches the rendered element in both forms', () => {
    const asButton = mount(JuliaButton, { attachTo: document.body });
    asButton.vm.focus();
    expect(document.activeElement).toBe(asButton.element);

    const asLink = mount(JuliaButton, {
      props: { href: '#somewhere' },
      attachTo: document.body
    });
    asLink.vm.focus();
    expect(document.activeElement).toBe(asLink.element);
  });
});
