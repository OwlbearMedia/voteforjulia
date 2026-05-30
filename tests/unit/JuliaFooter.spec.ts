import { mount, RouterLinkStub } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuliaFooter from '../../src/components/JuliaFooter.vue'
import { trackDonateClick, trackFooterIconClick } from '../../src/lib/analytics'

vi.mock('../../src/lib/analytics', () => ({
  trackDonateClick: vi.fn(),
  trackFooterIconClick: vi.fn(),
}))

describe('JuliaFooter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('tracks footer social icon clicks', async () => {
    const wrapper = mount(JuliaFooter, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const instagramLink = wrapper.find('a[aria-label="Julia on Instagram"]')
    await instagramLink.trigger('click')

    expect(trackFooterIconClick).toHaveBeenCalledWith(
      'https://www.instagram.com/voteforjuliahamann',
      'Julia on Instagram',
    )
  })

  it('tracks donate button clicks in the footer', async () => {
    const wrapper = mount(JuliaFooter, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const donateLink = wrapper.findAllComponents(RouterLinkStub)
      .find((link) => link.text() === 'Donate')

    expect(donateLink).toBeDefined()

    await donateLink!.trigger('click')

    expect(trackDonateClick).toHaveBeenCalledWith('footer', 'Donate')
  })
})
