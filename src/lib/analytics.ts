type GaEventParams = Record<string, string | number | boolean>;
type NewRelicAttributes = Record<string, string | number | boolean | null>;

interface NewRelicBrowserApi {
  addPageAction?: (name: string, attributes?: NewRelicAttributes) => void;
  noticeError?: (
    error: Error | string,
    customAttributes?: NewRelicAttributes,
  ) => void;
}

declare global {
  interface Window {
    gtag?: (
      command: "event",
      eventName: string,
      params?: Record<string, unknown>,
    ) => void;
    newrelic?: NewRelicBrowserApi;
  }
}

function getWindowObject(): Window | null {
  if ("window" in globalThis) {
    return globalThis.window;
  }

  return null;
}

export function trackGaEvent(
  eventName: string,
  params: GaEventParams = {},
): void {
  const windowObject = getWindowObject();
  if (!windowObject || typeof windowObject.gtag !== "function") {
    return;
  }

  windowObject.gtag("event", eventName, {
    ...params,
    transport_type: "beacon",
  });
}

export function trackDonateClick(linkLocation: string, linkText: string): void {
  trackGaEvent("donate_click", {
    link_location: linkLocation,
    link_text: linkText || "donate",
  });
}

export function trackFooterIconClick(href: string, ariaLabel: string): void {
  const normalizedHref = href.toLowerCase();
  const normalizedAriaLabel = ariaLabel.toLowerCase();

  let iconLabel = "other";
  if (
    normalizedHref.startsWith("mailto:") ||
    normalizedAriaLabel.includes("email")
  ) {
    iconLabel = "email";
  } else if (
    normalizedAriaLabel.includes("instagram") ||
    normalizedHref.includes("instagram.com")
  ) {
    iconLabel = "instagram";
  } else if (
    normalizedAriaLabel.includes("facebook") ||
    normalizedHref.includes("facebook.com")
  ) {
    iconLabel = "facebook";
  }

  trackGaEvent("footer_icon_click", {
    icon_label: iconLabel,
    icon_label_raw: ariaLabel || "unknown",
    link_url: href,
    link_type: normalizedHref.startsWith("mailto:") ? "email" : "social",
  });
}

export function trackVolunteerFormSubmit(status: "success" | "error"): void {
  const windowObject = getWindowObject();
  trackGaEvent("volunteer_form_submit", {
    form_id: "contact-form",
    form_location: windowObject ? windowObject.location.pathname : "",
    submission_status: status,
  });
}

export function trackVolunteerRequestBody(
  requestBody: Record<string, string>,
): void {
  const windowObject = getWindowObject();
  if (
    !windowObject?.newrelic ||
    typeof windowObject.newrelic.addPageAction !== "function"
  ) {
    return;
  }

  windowObject.newrelic.addPageAction("volunteer_form_request", {
    form_id: "contact-form",
    form_location: windowObject.location.pathname,
    request_body: JSON.stringify(requestBody),
  });
}

export function trackVolunteerSubmissionError(
  error: unknown,
  requestBody: Record<string, string>,
): void {
  const windowObject = getWindowObject();
  if (
    !windowObject?.newrelic ||
    typeof windowObject.newrelic.noticeError !== "function"
  ) {
    return;
  }

  const normalizedError =
    error instanceof Error
      ? error
      : typeof error === "string"
        ? error
        : "Volunteer form submission failed";

  windowObject.newrelic.noticeError(normalizedError, {
    form_id: "contact-form",
    form_location: windowObject.location.pathname,
    request_body: JSON.stringify(requestBody),
  });
}

export function trackPageView(path: string): void {
  const windowObject = getWindowObject();
  if (!windowObject) {
    return;
  }

  trackGaEvent("page_view", {
    page_path: path,
    page_location: `${windowObject.location.origin}${path}`,
    page_title: windowObject.document.title,
  });
}
