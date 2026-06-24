import { mount, RouterLinkStub } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHead } from '@unhead/vue';
import JuliaAbout from '../../src/pages/JuliaAbout.vue';
import JuliaDonate from '../../src/pages/JuliaDonate.vue';
import JuliaHome from '../../src/pages/JuliaHome.vue';
import JuliaSecretRecipe from '../../src/pages/JuliaSecretRecipe.vue';
import JuliaEvents from '../../src/pages/JuliaEvents.vue';
import JuliaVolunteer from '../../src/pages/JuliaVolunteer.vue';

vi.mock('@unhead/vue', () => ({
  useHead: vi.fn()
}));

const useHeadMock = vi.mocked(useHead);

describe('Page components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it('JuliaVolunteer renders volunteer form section and configures page SEO metadata', () => {
    const wrapper = mount(JuliaVolunteer, {
      global: {
        stubs: {
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

  it('JuliaDonate renders donation content and configures page SEO metadata', () => {
    const wrapper = mount(JuliaDonate, {
      global: {
        stubs: {
          'dbox-widget': true
        }
      }
    });

    expect(wrapper.text()).toContain('Donate now to help elect Julia as Mayor of Mankato!');
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
