/**
 * Lighthouse CI — run with `pnpm perf:lighthouse` after a build.
 *
 * CommonJS because @lhci/cli requires its config file rather than importing it,
 * and package.json sets "type": "module".
 *
 * See docs/performance.md for what these thresholds mean and how to move one.
 */

module.exports = {
  ci: {
    collect: {
      // Serve dist/ directly instead of `vite preview`, so what Lighthouse
      // measures is byte-for-byte what deploys. LHCI discovers every .html in
      // here, which means a new page is audited the moment it is built —
      // no URL list to forget to update.
      //
      // Note the URLs are `/meet-julia.html`, not `/meet-julia`. Extensionless
      // URLs are a LiteSpeed rewrite (public/.htaccess), not a property of the
      // files; the rewrite has no effect on any metric measured here.
      staticDistDir: './dist',
      // Auto-discovery silently stops at the first 5 files (alphabetically) —
      // `maxAutodiscoverUrls` defaults to 5, and nothing in the output says the
      // rest were skipped. 0 disables the cap. Listing the URLs by hand would
      // also work and would be worse: the list would go stale the next time a
      // page is added, in exactly the same silent way.
      maxAutodiscoverUrls: 0,
      // Median of three. Lighthouse's simulated throttling is deterministic in
      // principle, but page setup and the real third-party requests below are
      // not, and a single run drifts enough to fail a threshold on noise alone.
      numberOfRuns: 3,
      settings: {
        // No `preset`, so this is Lighthouse's default: emulated mobile with
        // simulated throttling. The realistic case for a campaign site shared
        // over text and social, and simulated throttling keeps the numbers
        // comparable between a laptop and a CI runner.
        //
        // These are fetched for real from the runner. Left in on purpose —
        // they are what visitors actually load, and their cost is exactly the
        // kind of regression this is here to catch.
        skipAudits: [
          // The static server sets no Cache-Control, so this measures LHCI's
          // server rather than LiteSpeed's headers (public/.htaccess).
          'uses-long-cache-ttl',
          // Same reason: the CSP and related headers are applied at the edge.
          'csp-xss',
          // localhost is HTTP/1.1; production is not.
          'uses-http2',
          // Canonical tags point at voteforjulia.com, which is correct in
          // production and always "wrong" when served from localhost.
          'canonical'
        ]
      }
    },
    assert: {
      // Every threshold below is a ratchet, not a target: it sits just past what
      // main measures, so the build fails when a change makes things worse and
      // never fails for the state we already shipped. When a fix improves one,
      // tighten the number in the same commit — otherwise the headroom quietly
      // becomes the new normal.
      //
      // The observed baseline the thresholds were calibrated from lives in
      // docs/performance.md and is deliberately NOT repeated here. It was, and
      // it drifted within a day: accessibility was fixed from 0.90 to 1.00 and
      // performance re-calibrated, and the copy here still claimed the old
      // numbers. One table, in the doc that explains it.
      assertions: {
        // 0.90, not 0.93-ish. The score is dominated by LCP, which is the header
        // logo fetched from ImageKit — a live third-party request whose timing
        // moves between sessions (2.97s and 3.25s on the same commit, and
        // `/` sits ~0.03 below every other route because of it). A threshold
        // pinned just under one session's minimum fails on someone else's CDN,
        // which is the fastest way to teach people to ignore this job.
        // Earning a tighter number back means making LCP not depend on that
        // fetch — a preconnect, or serving the logo from the origin.
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['error', { minScore: 1 }],
        'categories:seo': ['error', { minScore: 1 }],
        'categories:best-practices': ['error', { minScore: 1 }],

        // Lab metrics, as a backstop under the category score — the score is a
        // weighted blend and can stay green while one metric quietly doubles.
        // Headroom is widest on TBT, which is the metric most sensitive to how
        // loaded the runner is.
        'first-contentful-paint': ['error', { maxNumericValue: 2200 }],
        'largest-contentful-paint': ['error', { maxNumericValue: 3600 }],
        'total-blocking-time': ['error', { maxNumericValue: 200 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.05 }],

        // Third-party weight is reported, not enforced: Donorbox, GA4 and the
        // New Relic browser agent all change size without us doing anything,
        // and a failing build is the wrong way to find that out.
        'third-party-summary': 'warn',
        'unused-javascript': 'warn',
        'legacy-javascript': 'warn',
        'unminified-javascript': 'warn'
      }
    },
    upload: {
      // No LHCI server to talk to — reports land in .lighthouseci/ and CI
      // uploads them as a build artifact.
      target: 'filesystem',
      outputDir: './.lighthouseci'
    }
  }
};
