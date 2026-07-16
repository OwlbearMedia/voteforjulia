import { mount, RouterLinkStub } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHead } from '@unhead/vue';
import JuliaAbout from '../../src/pages/JuliaAbout.vue';
import JuliaDonate from '../../src/pages/JuliaDonate.vue';
import JuliaHome from '../../src/pages/JuliaHome.vue';
import JuliaSecretRecipe from '../../src/pages/JuliaSecretRecipe.vue';
import JuliaEvents from '../../src/pages/JuliaEvents.vue';
import JuliaNews from '../../src/pages/JuliaNews.vue';
import JuliaVolunteer from '../../src/pages/JuliaVolunteer.vue';
import JuliaYardSign from '../../src/pages/JuliaYardSign.vue';

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

  it('JuliaNews renders news coverage and configures page SEO metadata', () => {
    const wrapper = mount(JuliaNews);

    expect(wrapper.text()).toContain('Julia in the news');
    expect(wrapper.text()).toContain('Candidate for Mankato Mayor Hosts Campaign Launch Party');
    expect(wrapper.text()).toContain('RACE TO WATCH: Julia Hamann');
    expect(wrapper.text()).toContain(
      'RACE TO WATCH: Hamann hopes to bring conversation to City Council'
    );
    expect(wrapper.text()).toContain(
      'Mankato candidates officially file for office, with passing of Tuesday deadline'
    );
    expect(wrapper.text()).toContain(
      'Hamann, Bases look to bring new conversations to Mankato leadership'
    );
    expect(useHeadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'News | Julia Hamann for Mankato Mayor',
        link: expect.arrayContaining([
          expect.objectContaining({
            rel: 'canonical',
            href: 'https://voteforjulia.com/news'
          })
        ])
      })
    );
  });

  it('JuliaNews links each article out to its original source', () => {
    const wrapper = mount(JuliaNews);

    const expectedUrls = [
      'https://www.keyc.com/2026/06/30/candidate-mankato-mayor-hosts-campaign-launch-party/',
      'https://www.youtube.com/watch?v=UnVrel_BRfs',
      'https://www.mankatofreepress.com/news/local_news/race-to-watch-hamann-hopes-to-bring-conversation-to-city-council/article_167d04f5-3f33-4b85-a921-8e6e72a43b16.html',
      'https://www.keyc.com/2026/06/03/mankato-candidates-file-office/',
      'https://www.mankatofreepress.com/news/local_news/hamann-bases-look-to-bring-new-conversations-to-mankato-leadership/article_5c4264bb-8a5e-4d76-81e3-972ead716ebb.html'
    ];

    for (const url of expectedUrls) {
      const links = wrapper.findAll(`a[href="${url}"]`);
      expect(links.length).toBeGreaterThan(0);
      for (const link of links) {
        expect(link.attributes('target')).toBe('_blank');
        expect(link.attributes('rel')).toBe('noopener noreferrer');
      }
    }
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
