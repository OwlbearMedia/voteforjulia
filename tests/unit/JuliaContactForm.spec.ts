import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuliaContactForm from '../../src/components/JuliaContactForm.vue'
import { submitContactForm } from '../../src/lib/api'
import { trackVolunteerFormSubmit } from '../../src/lib/analytics'

vi.mock('../../src/lib/api', () => ({
  submitContactForm: vi.fn(),
}))

vi.mock('../../src/lib/analytics', () => ({
  trackVolunteerFormSubmit: vi.fn(),
}))

describe('JuliaContactForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows validation errors and does not submit when required fields are invalid', async () => {
    const wrapper = mount(JuliaContactForm)

    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Please enter your first name.')
    expect(wrapper.text()).toContain('Please enter a valid email address.')
    expect(submitContactForm).not.toHaveBeenCalled()
  })

  it('submits a valid payload and tracks success', async () => {
    vi.mocked(submitContactForm).mockResolvedValueOnce()

    const wrapper = mount(JuliaContactForm)

    await wrapper.find('#contact-first-name').setValue('Julia')
    await wrapper.find('#contact-last-name').setValue('Hamann')
    await wrapper.find('#contact-email').setValue('julia@example.com')
    await wrapper.find('#contact-phone').setValue('555-111-2222')
    await wrapper.find('#help-canvassing').setValue(true)
    await wrapper.find('#help-other-text').setValue('Door knocking coordination')
    await wrapper.find('#contact-message').setValue('Happy to help on weekends')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(submitContactForm).toHaveBeenCalledWith({
      firstName: 'Julia',
      lastName: 'Hamann',
      email: 'julia@example.com',
      phone: '555-111-2222',
      helpWays: 'Canvassing, Door knocking coordination',
      message: 'Happy to help on weekends',
    })
    expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('success')
  })

  it('shows API error message and tracks submission failure', async () => {
    vi.mocked(submitContactForm).mockRejectedValueOnce(new Error('Server unavailable'))

    const wrapper = mount(JuliaContactForm)

    await wrapper.find('#contact-first-name').setValue('Julia')
    await wrapper.find('#contact-email').setValue('julia@example.com')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(trackVolunteerFormSubmit).toHaveBeenCalledWith('error')
    expect(wrapper.text()).toContain('Server unavailable')
  })
})
