import { mount, RouterLinkStub } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuliaFooter from '../../src/components/JuliaFooter.vue'
import { trackDonateClick, trackFooterIconClick } from '../../src/lib/analytics'

vi.mock('../../src/lib/analytics', () => ({
  trackDonateClick: vi.fn(),
  trackFooterIconClick: vi.fn(),
}))

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function setInnerHeight(value: number) {
  Object.defineProperty(globalThis, 'innerHeight', {
    configurable: true,
    writable: true,
    value,
  })
}

function mockAnchorRect(anchorEl: HTMLElement, top: number) {
  vi.spyOn(anchorEl, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: top,
    top,
    left: 0,
    right: 300,
    bottom: top + 40,
    width: 300,
    height: 40,
    toJSON: () => ({}),
  } as DOMRect)
}

async function flushAnimationFrame() {
  if (typeof globalThis.requestAnimationFrame === 'function') {
    await new Promise<void>((resolve) => {
      globalThis.requestAnimationFrame(() => resolve())
    })
    return
  }

  await Promise.resolve()
}

describe('JuliaFooter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockMatchMedia(false)
    setInnerHeight(800)
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

  it('shows fixed teleported actions on mobile and hides in-footer actions', async () => {
    mockMatchMedia(true)

    const wrapper = mount(JuliaFooter, {
      attachTo: document.body,
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const anchorEl = wrapper.find('.footer-support-actions-anchor').element as HTMLElement
    mockAnchorRect(anchorEl, 1000)

    window.dispatchEvent(new Event('resize'))
    await flushAnimationFrame()
    await nextTick()

    const inFooterActions = wrapper.find('.footer-support-actions-anchor .footer-support-actions')
    expect(inFooterActions.classes()).toContain('footer-support-actions-hidden')
    expect(inFooterActions.attributes('aria-hidden')).toBe('true')

    const fixedActions = document.body.querySelector('.footer-support-actions-fixed')
    expect(fixedActions).not.toBeNull()

    wrapper.unmount()
  })

  it('keeps only in-footer actions visible on non-mobile viewports', async () => {
    mockMatchMedia(false)

    const wrapper = mount(JuliaFooter, {
      attachTo: document.body,
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const anchorEl = wrapper.find('.footer-support-actions-anchor').element as HTMLElement
    mockAnchorRect(anchorEl, 1000)

    window.dispatchEvent(new Event('resize'))
    await flushAnimationFrame()
    await nextTick()

    const inFooterActions = wrapper.find('.footer-support-actions-anchor .footer-support-actions')
    expect(inFooterActions.classes()).not.toContain('footer-support-actions-hidden')
    expect(inFooterActions.attributes('aria-hidden')).toBeUndefined()

    const fixedActions = document.body.querySelector('.footer-support-actions-fixed')
    expect(fixedActions).toBeNull()

    wrapper.unmount()
  })
})
