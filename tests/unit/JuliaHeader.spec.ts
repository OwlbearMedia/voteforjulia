import { mount, RouterLinkStub } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuliaHeader from '../../src/components/JuliaHeader.vue'
import { trackDonateClick } from '../../src/lib/analytics'

vi.mock('../../src/lib/analytics', () => ({
  trackDonateClick: vi.fn(),
}))

describe('JuliaHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the accessible heading from the title prop', () => {
    const wrapper = mount(JuliaHeader, {
      props: { title: 'Julia Hamann for Mankato Mayor' },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    expect(wrapper.find('h1.sr-only').text()).toBe('Julia Hamann for Mankato Mayor')
  })

  it('toggles mobile navigation visibility', async () => {
    const wrapper = mount(JuliaHeader, {
      props: { title: 'Test Title' },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const menu = wrapper.find('#main-menu')
    const toggleButton = wrapper.find('button.menu-toggle')

    expect(menu.classes()).not.toContain('open')
    expect(toggleButton.attributes('aria-expanded')).toBe('false')

    await toggleButton.trigger('click')

    expect(menu.classes()).toContain('open')
    expect(toggleButton.attributes('aria-expanded')).toBe('true')
  })

  it('tracks donate clicks and closes the menu', async () => {
    const wrapper = mount(JuliaHeader, {
      props: { title: 'Test Title' },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    await wrapper.find('button.menu-toggle').trigger('click')

    const donateLink = wrapper.findAllComponents(RouterLinkStub)
      .find((link) => link.text() === 'Donate')

    expect(donateLink).toBeDefined()

    await donateLink!.trigger('click')

    expect(trackDonateClick).toHaveBeenCalledWith('header', 'Donate')
    expect(wrapper.find('#main-menu').classes()).not.toContain('open')
  })
})
