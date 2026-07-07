import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  trackDonateClick,
  trackFooterIconClick,
  trackGaEvent,
  trackPageView,
  trackVolunteerFormSubmit,
  trackVolunteerRequestBody,
  trackVolunteerSubmissionError,
  trackYardSignFormSubmit,
  trackYardSignRequestBody,
  trackYardSignSubmissionError
} from '../../src/lib/analytics';

beforeEach(() => {
  delete (window as { gtag?: unknown }).gtag;
  delete (window as { newrelic?: unknown }).newrelic;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('trackGaEvent', () => {
  it('calls window.gtag with the event name, params, and beacon transport', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackGaEvent('test_event', { key: 'value' });

    expect(gtag).toHaveBeenCalledWith('event', 'test_event', {
      key: 'value',
      transport_type: 'beacon'
    });
  });

  it('merges an empty params object when none are provided', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackGaEvent('test_event');

    expect(gtag).toHaveBeenCalledWith('event', 'test_event', { transport_type: 'beacon' });
  });

  it('does nothing when window.gtag is not defined', () => {
    expect(() => trackGaEvent('test_event')).not.toThrow();
  });

  it('does nothing when window.gtag is not a function', () => {
    (window as { gtag?: unknown }).gtag = 'not-a-function';
    expect(() => trackGaEvent('test_event')).not.toThrow();
  });
});

describe('trackDonateClick', () => {
  it('fires a donate_click event with location and text', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackDonateClick('header', 'Donate Now');

    expect(gtag).toHaveBeenCalledWith('event', 'donate_click', {
      link_location: 'header',
      link_text: 'Donate Now',
      transport_type: 'beacon'
    });
  });

  it('falls back to "donate" when link text is empty', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackDonateClick('footer', '');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'donate_click',
      expect.objectContaining({ link_text: 'donate' })
    );
  });
});

describe('trackFooterIconClick', () => {
  it('identifies an Instagram link by href', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://www.instagram.com/voteforjuliahamann', 'Julia on Instagram');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'instagram', link_type: 'social' })
    );
  });

  it('identifies an Instagram link by aria label alone', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://example.com', 'Instagram profile');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'instagram' })
    );
  });

  it('identifies a Facebook link by href', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://www.facebook.com/profile.php?id=123', 'Julia on Facebook');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'facebook', link_type: 'social' })
    );
  });

  it('identifies an email link by mailto: scheme', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('mailto:info@example.com', 'Email Julia');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'email', link_type: 'email' })
    );
  });

  it('identifies an email link by aria label alone', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://example.com', 'Email the team');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'email' })
    );
  });

  it('falls back to "other" for unrecognized links', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://example.com', 'Some link');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({ icon_label: 'other' })
    );
  });

  it('includes the raw aria label and href in the event payload', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackFooterIconClick('https://www.instagram.com/voteforjuliahamann', 'Julia on Instagram');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'footer_icon_click',
      expect.objectContaining({
        icon_label_raw: 'Julia on Instagram',
        link_url: 'https://www.instagram.com/voteforjuliahamann'
      })
    );
  });
});

describe('trackVolunteerFormSubmit', () => {
  it('fires volunteer_form_submit with success status', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackVolunteerFormSubmit('success');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'volunteer_form_submit',
      expect.objectContaining({ form_id: 'contact-form', submission_status: 'success' })
    );
  });

  it('fires volunteer_form_submit with error status', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackVolunteerFormSubmit('error');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'volunteer_form_submit',
      expect.objectContaining({ submission_status: 'error' })
    );
  });
});

describe('trackVolunteerRequestBody', () => {
  it('calls newrelic.addPageAction with the serialised request body', () => {
    const addPageAction = vi.fn();
    window.newrelic = { addPageAction };

    trackVolunteerRequestBody({ firstName: 'Julia', email: 'julia@example.com' });

    expect(addPageAction).toHaveBeenCalledWith(
      'volunteer_form_request',
      expect.objectContaining({
        form_id: 'contact-form',
        request_body: JSON.stringify({ firstName: 'Julia', email: 'julia@example.com' })
      })
    );
  });

  it('does nothing when window.newrelic is not available', () => {
    expect(() => trackVolunteerRequestBody({ firstName: 'Julia' })).not.toThrow();
  });

  it('does nothing when newrelic.addPageAction is not a function', () => {
    window.newrelic = {};
    expect(() => trackVolunteerRequestBody({ firstName: 'Julia' })).not.toThrow();
  });
});

describe('trackVolunteerSubmissionError', () => {
  it('passes an Error instance directly to newrelic.noticeError', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };
    const error = new Error('Network failure');

    trackVolunteerSubmissionError(error, { firstName: 'Julia' });

    expect(noticeError).toHaveBeenCalledWith(
      error,
      expect.objectContaining({ form_id: 'contact-form' })
    );
  });

  it('passes a string error directly to newrelic.noticeError', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };

    trackVolunteerSubmissionError('something went wrong', { firstName: 'Julia' });

    expect(noticeError).toHaveBeenCalledWith('something went wrong', expect.any(Object));
  });

  it('normalises an unknown error type to the default message', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };

    trackVolunteerSubmissionError({ code: 500 }, { firstName: 'Julia' });

    expect(noticeError).toHaveBeenCalledWith(
      'Volunteer form submission failed',
      expect.any(Object)
    );
  });

  it('includes the serialised request body in the attributes', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };

    trackVolunteerSubmissionError(new Error('oops'), { firstName: 'Julia', email: 'j@example.com' });

    expect(noticeError).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        request_body: JSON.stringify({ firstName: 'Julia', email: 'j@example.com' })
      })
    );
  });

  it('does nothing when window.newrelic is not available', () => {
    expect(() =>
      trackVolunteerSubmissionError(new Error('fail'), { firstName: 'Julia' })
    ).not.toThrow();
  });

  it('does nothing when newrelic.noticeError is not a function', () => {
    window.newrelic = {};
    expect(() =>
      trackVolunteerSubmissionError(new Error('fail'), { firstName: 'Julia' })
    ).not.toThrow();
  });
});

describe('trackYardSignFormSubmit', () => {
  it('fires yard_sign_form_submit with success status', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackYardSignFormSubmit('success');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'yard_sign_form_submit',
      expect.objectContaining({ form_id: 'yard-sign-form', submission_status: 'success' })
    );
  });

  it('fires yard_sign_form_submit with error status', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackYardSignFormSubmit('error');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'yard_sign_form_submit',
      expect.objectContaining({ submission_status: 'error' })
    );
  });
});

describe('trackYardSignRequestBody', () => {
  it('calls newrelic.addPageAction with the serialised request body', () => {
    const addPageAction = vi.fn();
    window.newrelic = { addPageAction };

    trackYardSignRequestBody({ firstName: 'Julia', address: '123 Main St' });

    expect(addPageAction).toHaveBeenCalledWith(
      'yard_sign_form_request',
      expect.objectContaining({
        form_id: 'yard-sign-form',
        request_body: JSON.stringify({ firstName: 'Julia', address: '123 Main St' })
      })
    );
  });

  it('does nothing when window.newrelic is not available', () => {
    expect(() => trackYardSignRequestBody({ firstName: 'Julia' })).not.toThrow();
  });
});

describe('trackYardSignSubmissionError', () => {
  it('passes an Error instance directly to newrelic.noticeError', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };
    const error = new Error('Network failure');

    trackYardSignSubmissionError(error, { firstName: 'Julia' });

    expect(noticeError).toHaveBeenCalledWith(
      error,
      expect.objectContaining({ form_id: 'yard-sign-form' })
    );
  });

  it('normalises an unknown error type to the default message', () => {
    const noticeError = vi.fn();
    window.newrelic = { noticeError };

    trackYardSignSubmissionError({ code: 500 }, { firstName: 'Julia' });

    expect(noticeError).toHaveBeenCalledWith(
      'Yard sign form submission failed',
      expect.any(Object)
    );
  });

  it('does nothing when window.newrelic is not available', () => {
    expect(() =>
      trackYardSignSubmissionError(new Error('fail'), { firstName: 'Julia' })
    ).not.toThrow();
  });
});

describe('trackPageView', () => {
  it('fires a page_view event with the path and page title', () => {
    const gtag = vi.fn();
    window.gtag = gtag;

    trackPageView('/meet-julia');

    expect(gtag).toHaveBeenCalledWith(
      'event',
      'page_view',
      expect.objectContaining({ page_path: '/meet-julia' })
    );
  });
});
