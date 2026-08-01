import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { initNewRelic, initNewRelicWhenReady } from '../../src/lib/newrelic';

const MockBrowserAgent = vi.fn();

vi.mock('@newrelic/browser-agent/loaders/browser-agent', () => ({
  BrowserAgent: MockBrowserAgent
}));

describe('newrelic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initNewRelic', () => {
    it('constructs BrowserAgent with the configured options', async () => {
      initNewRelic();
      await flushPromises();

      expect(MockBrowserAgent).toHaveBeenCalledOnce();
      expect(MockBrowserAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          info: expect.objectContaining({
            applicationID: '653419329',
            beacon: 'bam.nr-data.net',
            errorBeacon: 'bam.nr-data.net'
          }),
          loader_config: expect.objectContaining({
            accountID: 8127277,
            agentID: 653419329
          })
        })
      );
    });

    it('allows trace headers to reach both API origins', async () => {
      // Distributed tracing across origins needs this list AND the matching
      // Access-Control-Allow-Headers in api/app.py. Drop either and nothing
      // breaks loudly — browser and API traces just stop correlating, which is
      // only noticed when someone goes looking for a trace that should exist.
      initNewRelic();
      await flushPromises();

      expect(MockBrowserAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          init: expect.objectContaining({
            distributed_tracing: {
              allowed_origins: [
                'https://api.voteforjulia.com',
                'https://test-api.voteforjulia.com'
              ],
              enabled: true
            }
          })
        })
      );
    });
  });

  describe('initNewRelicWhenReady', () => {
    it('initializes immediately when the DOM is already loaded', async () => {
      // jsdom default readyState is 'complete'
      initNewRelicWhenReady();
      await flushPromises();

      expect(MockBrowserAgent).toHaveBeenCalledOnce();
    });

    it('defers initialization until DOMContentLoaded when the document is still loading', async () => {
      Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });

      try {
        initNewRelicWhenReady();
        expect(MockBrowserAgent).not.toHaveBeenCalled();

        document.dispatchEvent(new Event('DOMContentLoaded'));
        await flushPromises();

        expect(MockBrowserAgent).toHaveBeenCalledOnce();
      } finally {
        Object.defineProperty(document, 'readyState', { value: 'complete', configurable: true });
      }
    });

    it('initializes exactly once even if DOMContentLoaded fires multiple times', async () => {
      Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });

      try {
        initNewRelicWhenReady();
        document.dispatchEvent(new Event('DOMContentLoaded'));
        await flushPromises();

        document.dispatchEvent(new Event('DOMContentLoaded'));
        await flushPromises();

        expect(MockBrowserAgent).toHaveBeenCalledOnce();
      } finally {
        Object.defineProperty(document, 'readyState', { value: 'complete', configurable: true });
      }
    });
  });
});
