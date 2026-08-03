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
      // Enforced thresholds are a ratchet, not a target: each sits just past
      // what main measures, so the build fails when a change makes things worse
      // and never fails for the state we already shipped. When a fix improves
      // one, tighten it in the same commit — otherwise the headroom quietly
      // becomes the new normal.
      //
      // The observed baseline these were calibrated from lives in
      // docs/performance.md and is deliberately NOT repeated here. It was, and
      // it drifted within a day: accessibility was fixed from 0.90 to 1.00 and
      // performance re-calibrated, and the copy here still claimed the old
      // numbers. One table, in the doc that explains it.
      // What fails the build is decided by measured stability on the CI runner,
      // not by importance. Across the 24 runs of the first CI execution
      // (8 routes x 3), these were bit-identical every single time — so a change
      // in them is a change we made:
      //
      //   accessibility 1.00-1.00   seo 1.00-1.00
      //   best-practices 1.00-1.00  CLS 0.000-0.000
      //
      // ...while every timing metric ranged far past its threshold on at least
      // one run:
      //
      //   performance 0.49-0.96   FCP 1362-3951ms
      //   LCP 2579-7530ms         TBT 132-566ms
      //
      // Those spreads are the runner, not the site: TBT measured 11-13ms on a
      // laptop against 132-566ms here, on identical bytes. Asserting on them
      // would produce a job that fails randomly, and a job that fails randomly
      // gets re-run until green — which is worse than one that only warns,
      // because it looks like enforcement while teaching people to bypass it.
      //
      // The deterministic half of this gate is the bundle budget
      // (scripts/check-bundle-budget.mjs): byte-exact, zero variance between
      // laptop and runner. That is what actually guards the chunking and
      // CSS-inlining work ADR-0015 was written about.
      assertions: {
        // Enforced — zero observed variance.
        'categories:accessibility': ['error', { minScore: 1 }],
        'categories:seo': ['error', { minScore: 1 }],
        'categories:best-practices': ['error', { minScore: 1 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.05 }],

        // Advisory — real signal, unreliable as a gate. The numbers are set
        // around the CI medians so a warning means "drifted", not "unlucky".
        // Promoting any of these to `error` requires removing the variance
        // first, not just widening the number: LCP is the ImageKit logo fetch
        // (a preconnect, or serving it from the origin), and TBT/performance
        // are CPU contention on a shared runner.
        'categories:performance': ['warn', { minScore: 0.9 }],
        'first-contentful-paint': ['warn', { maxNumericValue: 2200 }],
        'largest-contentful-paint': ['warn', { maxNumericValue: 3600 }],
        'total-blocking-time': ['warn', { maxNumericValue: 400 }],

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
