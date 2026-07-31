import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { vueCompilerOptions } from './vue-compiler-options';

export default defineConfig({
  // Same compiler options as the real build so templates behave identically
  // under test — see vue-compiler-options.ts.
  plugins: [vue({ template: { compilerOptions: vueCompilerOptions } })],
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
