import { mount, RouterLinkStub } from '@vue/test-utils';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import JuliaContactForm from '../../src/components/JuliaContactForm.vue';
import JuliaYardSignForm from '../../src/components/JuliaYardSignForm.vue';
import { submitContactForm, submitYardSignForm } from '../../src/lib/api';

vi.mock('../../src/lib/api', () => ({
  submitContactForm: vi.fn(),
  submitYardSignForm: vi.fn(),
  API_BASE_URL: 'https://api.example.test'
}));

vi.mock('../../src/lib/analytics', () => ({
  trackVolunteerFormSubmit: vi.fn(),
  trackVolunteerRequestBody: vi.fn(),
  trackVolunteerSubmissionError: vi.fn(),
  trackYardSignFormSubmit: vi.fn(),
  trackYardSignRequestBody: vi.fn(),
  trackYardSignSubmissionError: vi.fn()
}));

// `import.meta.url` is not a file URL under jsdom, so the usual fileURLToPath
// idiom throws; resolve from cwd as `scripts/check-bundle-budget.mjs` does.
const STYLESHEET = readFileSync(resolve(process.cwd(), 'src/style.css'), 'utf-8');

// JuliaYardSignForm renders a RouterLink and the unit suite installs no router.
// Stubbed for both so the shared `it.each` cases mount identically.
const mountForm = (component: Parameters<typeof mount>[0]) =>
  mount(component, { global: { stubs: { RouterLink: RouterLinkStub } } });

/**
 * The honeypot (ADR-0016) is the one feature here that can reject a real
 * supporter, and a screen-reader user is most at risk. These pin the properties
 * that prevent it, so a later markup or stylesheet "tidy-up" fails here rather
 * than in someone's inbox.
 */
describe('honeypot accessibility', () => {
  /**
   * The whole safety argument in one assertion: `display: none` removes the
   * element from the accessibility tree, while the off-screen idiom `.sr-only`
   * uses keeps it announced. Swapping one for the other reads as an equivalent
   * refactor and would make this a trap only screen-reader users fall into.
   */
  it('hides the honeypot with display:none rather than positioning it off-screen', () => {
    const rule = /\.honeypot-field\s*\{([^}]*)\}/.exec(STYLESHEET);

    expect(rule, '.honeypot-field must be defined in src/style.css').not.toBeNull();

    const declarations = rule![1];
    expect(declarations).toMatch(/display:\s*none/);
    // The off-screen idiom, in any of its usual spellings.
    expect(declarations).not.toMatch(/position:\s*absolute/);
    expect(declarations).not.toMatch(/-?\d{4,}px/);
    expect(declarations).not.toMatch(/clip|clip-path|sr-only/);
  });

  it.each([
    ['JuliaContactForm', JuliaContactForm, 'contact-referral-code'],
    ['JuliaYardSignForm', JuliaYardSignForm, 'yard-sign-referral-code']
  ])('%s puts the honeypot in a display:none wrapper, never .sr-only', (_name, component, id) => {
    const wrapper = mountForm(component);
    const field = wrapper.find(`#${id}`);

    expect(field.exists()).toBe(true);
    expect(field.attributes('name')).toBe('referralCode');

    const container = field.element.closest('div');
    expect(container?.className).toContain('honeypot-field');
    // `.sr-only` anywhere in this subtree would defeat the point entirely.
    expect(container?.className).not.toContain('sr-only');
  });

  it.each([
    ['JuliaContactForm', JuliaContactForm, 'contact-referral-code'],
    ['JuliaYardSignForm', JuliaYardSignForm, 'yard-sign-referral-code']
  ])(
    '%s keeps the honeypot out of the tab order and away from autofill',
    (_name, component, id) => {
      const wrapper = mountForm(component);
      const field = wrapper.find(`#${id}`);

      // A keyboard user tabbing through the form must never land in it.
      expect(field.attributes('tabindex')).toBe('-1');
      // The real residual risk is autofill, not screen readers: a password
      // manager filling this would reject a genuine submission.
      expect(field.attributes('autocomplete')).toBe('off');
      expect(field.attributes('name')).not.toMatch(
        /^(name|email|phone|tel|address|organization|nickname|url|username)$/i
      );
    }
  );

  it.each([
    ['JuliaContactForm', JuliaContactForm, 'contact-referral-code'],
    ['JuliaYardSignForm', JuliaYardSignForm, 'yard-sign-referral-code']
  ])('%s labels the honeypot so a missing stylesheet degrades safely', (_name, component, id) => {
    const wrapper = mountForm(component);

    // If style.css fails to load the field becomes visible, and a labelled input
    // is recoverable where an unexplained box is not. Also keeps Lighthouse's
    // `label` audit green in that state, which CI gates on.
    const label = wrapper.find(`label[for="${id}"]`);
    expect(label.exists()).toBe(true);
    expect(label.text()).toMatch(/leave this field empty/i);
  });
});

describe('honeypot behaviour', () => {
  it('sends an empty honeypot on a normal contact submission', async () => {
    vi.mocked(submitContactForm).mockResolvedValueOnce();
    const wrapper = mountForm(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');
    await wrapper.find('form').trigger('submit');

    // Empty, and present. The API treats blank and absent alike, but sending it
    // is what extends the check to a headless browser that fills every input.
    expect(submitContactForm).toHaveBeenCalledWith(expect.objectContaining({ referralCode: '' }));
  });

  it('forwards a filled honeypot so the API can refuse it', async () => {
    vi.mocked(submitContactForm).mockResolvedValueOnce();
    const wrapper = mountForm(JuliaContactForm);

    await wrapper.find('#contact-first-name').setValue('Julia');
    await wrapper.find('#contact-email').setValue('julia@example.com');
    await wrapper.find('#contact-referral-code').setValue('https://spam.example');
    await wrapper.find('form').trigger('submit');

    // The client deliberately does not reject this itself: that would name the
    // field for the bot and move the decision to code the attacker controls.
    expect(submitContactForm).toHaveBeenCalledWith(
      expect.objectContaining({ referralCode: 'https://spam.example' })
    );
  });

  it('sends an empty honeypot on a normal yard-sign submission', async () => {
    vi.mocked(submitYardSignForm).mockResolvedValueOnce();
    const wrapper = mountForm(JuliaYardSignForm);

    await wrapper.find('#yard-sign-first-name').setValue('Julia');
    await wrapper.find('#yard-sign-email').setValue('julia@example.com');
    await wrapper.find('#yard-sign-address').setValue('123 Main St, Mankato, MN 56001');
    await wrapper.find('form').trigger('submit');

    expect(submitYardSignForm).toHaveBeenCalledWith(expect.objectContaining({ referralCode: '' }));
  });
});
