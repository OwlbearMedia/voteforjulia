import { ViteSSG } from 'vite-ssg'
import { BrowserAgent } from '@newrelic/browser-agent/loaders/browser-agent'

import './style.css';
import App from './App.vue';
import { routes } from './lib/routes';
import { trackPageView } from './lib/analytics';

const options = {
  "info": {
    "applicationID": 653419329,
    "beacon": "bam.nr-data.net",
    "errorBeacon": "bam.nr-data.net",
    "licenseKey": "NRJS-8688cc793ecfb998d0b",
    "sa": 1
  },
  "init": {
    "ajax": {
      "deny_list": [
        "bam.nr-data.net"
      ]
    },
    "browser_consent_mode": {
      "enabled": false
    },
    "distributed_tracing": {
      "enabled": true
    },
    "performance": {
      "capture_detail": false,
      "capture_marks": false,
      "capture_measures": true
    },
    "privacy": {
      "cookies_enabled": true
    }
  },
  "loader_config": {
    "accountID": 8127277,
    "agentID": 653419329,
    "applicationID": 653419329,
    "licenseKey": "NRJS-8688cc793ecfb998d0b",
    "trustKey": 8127277
  }
}

// The agent loader code executes immediately on instantiation.
// @ts-ignore-next-line
const nrba = new BrowserAgent(options)

// Remaining code
export const createApp = ViteSSG(
  App,
  {
    routes,
    scrollBehavior(to, _from, savedPosition) {
      if (savedPosition) {
        return savedPosition;
      }

      if (to.hash) {
        return new Promise((resolve) => {
          setTimeout(() => {
            const targetElement = document.querySelector(to.hash);
            if (!targetElement) {
              resolve({ top: 0 });
              return;
            }

            const headerElement = document.querySelector('header');
            const headerHeight = headerElement ? headerElement.getBoundingClientRect().height : 0;
            const targetTop = targetElement.getBoundingClientRect().top + window.scrollY;
            const scrollTop = Math.max(targetTop - headerHeight - 8, 0);

            resolve({
              top: scrollTop,
            });
          }, 0);
        });
      }

      return { top: 0 };
    },
  },
  ({ router }) => {
  if (import.meta.env.SSR) {
    return;
  }

  router.isReady().then(() => {
    trackPageView(router.currentRoute.value.fullPath);
  });

  router.afterEach((to) => {
    trackPageView(to.fullPath);
  });
});
