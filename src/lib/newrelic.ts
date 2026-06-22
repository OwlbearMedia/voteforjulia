// Single source of truth for the New Relic browser agent configuration.
// These values are public by design (the agent runs in the browser), so it is
// fine for them to live in client code. Typing against the constructor's own
// parameter type removes the need for the `@ts-ignore` the inline version used.
// The `typeof import(...)` query references the constructor type without
// emitting a runtime import, so the agent stays lazily loaded below.
type BrowserAgentOptions = ConstructorParameters<
  typeof import('@newrelic/browser-agent/loaders/browser-agent').BrowserAgent
>[0];

const NEW_RELIC_OPTIONS: BrowserAgentOptions = {
  info: {
    applicationID: '653419329',
    beacon: 'bam.nr-data.net',
    errorBeacon: 'bam.nr-data.net',
    licenseKey: 'NRJS-8688cc793ecfb998d0b',
    sa: 1
  },
  init: {
    ajax: {
      deny_list: ['bam.nr-data.net']
    },
    browser_consent_mode: {
      enabled: false
    },
    distributed_tracing: {
      enabled: true
    },
    performance: {
      capture_detail: false,
      capture_marks: false,
      capture_measures: true
    },
    privacy: {
      cookies_enabled: true
    }
  },
  loader_config: {
    accountID: 8127277,
    agentID: 653419329,
    applicationID: '653419329',
    licenseKey: 'NRJS-8688cc793ecfb998d0b',
    trustKey: 8127277
  }
};

/**
 * Lazily loads and starts the New Relic browser agent. The dynamic import keeps
 * the agent out of the critical render path. Constructing the agent registers it
 * globally via side effect, so no reference needs to be retained.
 */
export function initNewRelic(): void {
  void import('@newrelic/browser-agent/loaders/browser-agent').then(({ BrowserAgent }) => {
    new BrowserAgent(NEW_RELIC_OPTIONS); // NOSONAR S1848 — constructor registers the agent globally as a side effect
  });
}

/**
 * Starts New Relic once the document is ready: immediately if the DOM has
 * already finished parsing, otherwise on `DOMContentLoaded`.
 */
export function initNewRelicWhenReady(): void {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNewRelic, { once: true });
  } else {
    initNewRelic();
  }
}
