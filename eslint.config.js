import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import pluginVue from 'eslint-plugin-vue';
import configPrettier from 'eslint-config-prettier';

// ESLint 9 flat config. Pairs with Prettier (formatting stays Prettier's job;
// `eslint-config-prettier` disables any stylistic rules that would conflict).
export default tseslint.config(
  {
    // Build output, caches, and the Python virtualenv (which vendors its own
    // JS). node_modules is ignored by ESLint by default, but listed for clarity.
    ignores: [
      '**/node_modules/**',
      'dist/**',
      'coverage/**',
      '**/.vite/**',
      '**/.venv/**',
      '**/venv/**',
      '**/__pycache__/**'
    ]
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    // Let the Vue parser hand <script lang="ts"> blocks to the TS parser.
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser
      }
    }
  },
  {
    files: ['src/**/*.{ts,vue}'],
    languageOptions: {
      globals: {
        ...globals.browser
      }
    }
  },
  {
    // Build/test config and deploy scripts run in Node.
    files: ['*.config.{ts,js,mjs}', 'scripts/**/*.mjs', 'vitest.setup.ts'],
    languageOptions: {
      globals: {
        ...globals.node
      }
    }
  },
  {
    rules: {
      // Allow intentionally unused args/vars when prefixed with `_`.
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }]
    }
  },
  configPrettier
);
