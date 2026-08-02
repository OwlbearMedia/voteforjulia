import { mount, RouterLinkStub } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHead } from '@unhead/vue';
import JuliaAbout from '../../src/pages/JuliaAbout.vue';
import JuliaDonate from '../../src/pages/JuliaDonate.vue';
import JuliaHome from '../../src/pages/JuliaHome.vue';
import JuliaSecretRecipe from '../../src/pages/JuliaSecretRecipe.vue';
import JuliaEvents from '../../src/pages/JuliaEvents.vue';
import JuliaEndorsements from '../../src/pages/JuliaEndorsements.vue';
import JuliaVolunteer from '../../src/pages/JuliaVolunteer.vue';
import JuliaYardSign from '../../src/pages/JuliaYardSign.vue';

vi.mock('@unhead/vue', () => ({
  useHead: vi.fn()
}));

const useHeadMock = vi.mocked(useHead);

// JuliaDonate appends this to <head> on mount, and the shared jsdom cleanup in
// vitest.setup.ts only resets <body> — so without an explicit reset it leaks
// into every later test in the file.
const DONORBOX_LOADER = 'script[src="https://donorbox.org/widgets.js"]';

describe('Page components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.head.querySelectorAll(DONORBOX_LOADER).forEach((el) => el.remove());
  });

  it('JuliaHome renders key content and configures home SEO metadata', () => {
    const wrapper = mount(JuliaHome, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
          JuliaContactForm: true
        }
      }
    });

    expect(wrapper.text()).toContain('Meet Julia');
    expect(wrapper.text()).toContain('Environmental Justice and Sustainability');
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Home | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/'
          })
        ]),
        script: expect.arrayContaining([
          expect.objectContaining({
            type: 'application/ld+json'
          })
        ])
      })
    );
  });

  it('JuliaAbout renders biography content and configures page SEO metadata', () => {
    const wrapper = mount(JuliaAbout);

    expect(wrapper.text()).toContain('Who is Julia?');
    expect(wrapper.text()).toContain('Inspiration for Running for Mayor');
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Meet Julia | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/meet-julia'
          })
        ])
      })
    );
  });

  it('JuliaEvents renders events content and configures page SEO metadata', () => {
    const wrapper = mount(JuliaEvents);

    expect(wrapper.text()).toContain('Upcoming Events');
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Events | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/events'
          })
        ])
      })
    );
  });

  it('JuliaEndorsements renders endorsement content and configures page SEO metadata', () => {
    const wrapper = mount(JuliaEndorsements);

    expect(wrapper.text()).toContain('Endorsements');
    expect(wrapper.text()).toContain(
      'Endorsements Julia is grateful to be endorsed by: Indivisible St. Peter/Greater Mankato'
    );
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Endorsements | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/endorsements'
          })
        ])
      })
    );
  });

  it('JuliaVolunteer renders volunteer form section and configures page SEO metadata', () => {
    const wrapper = mount(JuliaVolunteer, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
          JuliaContactForm: true
        }
      }
    });

    expect(wrapper.text()).toContain(
      'Join the campaign team to help with outreach, events, and voter engagement.'
    );
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Volunteer | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/volunteer'
          })
        ])
      })
    );
  });

  it('JuliaYardSign renders yard sign form section and configures page SEO metadata', () => {
    const wrapper = mount(JuliaYardSign, {
      global: {
        stubs: {
          JuliaYardSignForm: true
        }
      }
    });

    expect(wrapper.text()).toContain(
      'Yard signs are a great way to show your support and help spread the word about Julia’s campaign.'
    );
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Yard Sign | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/yard-signs'
          })
        ])
      })
    );
  });

  // The page links to /yard-signs, so RouterLink needs stubbing or every mount
  // logs a resolution warning.
  const mountDonate = () =>
    mount(JuliaDonate, { global: { stubs: { RouterLink: RouterLinkStub } } });

  it('JuliaDonate renders donation content and configures page SEO metadata', () => {
    const wrapper = mountDonate();

    expect(wrapper.text()).toContain('Donate now to help elect Julia as Mayor of Mankato!');
    // Written as raw markup so the browser parses it, rather than compiled into
    // the render function — Vue's createElement trips Donorbox's constructor.
    // See the comment on donorboxWidget in JuliaDonate.vue.
    const widget = wrapper.find('dbox-widget');
    expect(widget.exists()).toBe(true);
    expect(widget.attributes('campaign')).toBe('julia-hamann-for-mankato-mayor');
    expect(widget.attributes('type')).toBe('donation_form');
    expect(widget.attributes('enable-auto-scroll')).toBe('true');
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Donate | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/donate'
          })
        ])
      })
    );
  });

  describe('JuliaDonate Donorbox loader', () => {
    // The loader must not sit in <head> at page-load time: when it beat
    // hydration it upgraded <dbox-widget> early, Vue saw a mismatch, re-created
    // the element, and the vendor constructor threw. Preload without executing.
    it('preloads the loader from <head> but never executes it there', () => {
      mountDonate();

      const head = useHeadMock.mock.calls[0][0] as {
        link: { rel: string; href: string }[];
        script: { src?: string }[];
      };

      expect(head.link).toContainEqual({
        rel: 'modulepreload',
        href: 'https://donorbox.org/widgets.js'
      });
      expect(head.script.some((entry) => entry.src === 'https://donorbox.org/widgets.js')).toBe(
        false
      );
    });

    it('appends the loader on mount, once', () => {
      expect(document.head.querySelectorAll(DONORBOX_LOADER)).toHaveLength(0);

      mountDonate();

      const loader = document.head.querySelector<HTMLScriptElement>(DONORBOX_LOADER);
      expect(loader).not.toBeNull();
      expect(loader?.type).toBe('module');
      expect(loader?.async).toBe(true);

      // Remounting (a second SPA visit to /donate) must not stack loaders.
      mountDonate();
      expect(document.head.querySelectorAll(DONORBOX_LOADER)).toHaveLength(1);
    });
  });

  it('JuliaSecretRecipe renders recipe content and configures page SEO metadata', () => {
    const wrapper = mount(JuliaSecretRecipe);

    expect(wrapper.text()).toContain('Shrimp Salad Supreme');
    expect(wrapper.text()).toContain('Mix the lemon Jello with the boiling water');
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Secret Recipe | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/secret-recipe'
          })
        ])
      })
    );
  });
});
