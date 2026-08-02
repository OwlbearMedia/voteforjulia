import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  // No template compilerOptions, matching vite.config.ts — templates have to
  // compile identically here and in the real build, so any option added there
  // has to be added here too.
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['tests/**/*.spec.ts'],
    coverage: {
      provider: 'v8',
      // Baseline visibility only — no thresholds, so coverage never fails CI yet.
      reporter: ['text', 'text-summary', 'json-summary', 'lcov', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,vue}'],
      // src/dev is the local-only Swagger UI entry — never built, never shipped,
      // so it would only ever report as uncovered site code.
      exclude: ['src/main.ts', 'src/env.d.ts', 'src/**/*.d.ts', 'src/dev/**']
    }
  }
});
