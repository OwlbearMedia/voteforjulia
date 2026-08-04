import { ViteSSG } from 'vite-ssg';
import { configure } from 'vue-gtag';

import './style.css';
import App from './App.vue';
import { routes } from './lib/routes';
import { trackPageView } from './lib/analytics';
import { initNewRelicWhenReady } from './lib/newrelic';

if (!import.meta.env.SSR) {
  configure({
    tagId: 'G-4WYNB1ECZQ',
    config: {
      send_page_view: false
    }
  });
}

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
              top: scrollTop
            });
          }, 0);
        });
      }

      return { top: 0 };
    }
  },
  ({ router }) => {
    if (import.meta.env.SSR) {
      return;
    }

    // Defer the New Relic agent so it never blocks the initial render.
    initNewRelicWhenReady();

    // `afterEach` alone covers every navigation *including the first*. vite-ssg
    // invokes this callback before `app.use(router)`, so the hook is registered
    // before the initial navigation starts and therefore fires for it. Pairing
    // it with a `router.isReady()` handler — the obvious-looking way to catch
    // the entry page — sent two identical page_view events for every cold load
    // and double-counted every entry page in GA4.
    router.afterEach((to) => {
      trackPageView(to.fullPath);
    });
  }
);
