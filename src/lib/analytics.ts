type GaEventParams = Record<string, string | number | boolean>;

declare global {
  interface Window {
    gtag?: (
      command: 'event',
      eventName: string,
      params?: Record<string, unknown>,
    ) => void;
  }
}

function getWindowObject(): Window | null {
  if ('window' in globalThis) {
    return globalThis.window;
  }

  return null;
}

export function trackGaEvent(eventName: string, params: GaEventParams = {}): void {
  const windowObject = getWindowObject();
  if (!windowObject || typeof windowObject.gtag !== 'function') {
    return;
  }

  windowObject.gtag('event', eventName, {
    ...params,
    transport_type: 'beacon',
  });
}

export function trackDonateClick(linkLocation: string, linkText: string): void {
  trackGaEvent('donate_click', {
    link_location: linkLocation,
    link_text: linkText || 'donate',
  });
}

export function trackFooterIconClick(
  href: string,
  ariaLabel: string,
): void {
  const normalizedHref = href.toLowerCase();
  const normalizedAriaLabel = ariaLabel.toLowerCase();

  let iconLabel = 'other';
  if (normalizedHref.startsWith('mailto:') || normalizedAriaLabel.includes('email')) {
    iconLabel = 'email';
  } else if (
    normalizedAriaLabel.includes('instagram') ||
    normalizedHref.includes('instagram.com')
  ) {
    iconLabel = 'instagram';
  } else if (
    normalizedAriaLabel.includes('facebook') ||
    normalizedHref.includes('facebook.com')
  ) {
    iconLabel = 'facebook';
  }

  trackGaEvent('footer_icon_click', {
    icon_label: iconLabel,
    icon_label_raw: ariaLabel || 'unknown',
    link_url: href,
    link_type: normalizedHref.startsWith('mailto:') ? 'email' : 'social',
  });
}

export function trackVolunteerFormSubmit(status: 'success' | 'error'): void {
  const windowObject = getWindowObject();
  trackGaEvent('volunteer_form_submit', {
    form_id: 'contact-form',
    form_location: windowObject ? windowObject.location.pathname : '',
    submission_status: status,
  });
}

export function trackPageView(path: string): void {
  const windowObject = getWindowObject();
  if (!windowObject) {
    return;
  }

  trackGaEvent('page_view', {
    page_path: path,
    page_location: `${windowObject.location.origin}${path}`,
    page_title: windowObject.document.title,
  });
}
