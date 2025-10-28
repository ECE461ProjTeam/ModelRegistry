/**
 * 🧠 ESLint Flat Config for a React + Vite project (ESLint v9+)
 *
 * This file uses ESLint’s new "flat config" format.
 * Instead of a single object with `"extends"`, we now export an array of
 * configuration objects. ESLint applies them in order (top → bottom).
 *
 * Main goals of this config:
 * 1. Use ESLint’s built-in recommended rules for JavaScript.
 * 2. Enable React and React Hooks linting.
 * 3. Integrate with Vite’s React Refresh plugin for fast dev feedback.
 * 4. Define language options (browser environment, ECMAScript features).
 * 5. Add a custom rule for unused variables.
 *
 * Note: No `extends` or `defineConfig` — this is the modern, correct flat-config syntax.
 */

import js from '@eslint/js'                     // ✅ Provides ESLint’s built-in recommended rules.
import globals from 'globals'                   // ✅ Exposes predefined global variables (like `window`, `document`, etc.)
import reactHooks from 'eslint-plugin-react-hooks' // ✅ Enforces React Hooks rules (e.g., correct hook usage).
import reactRefresh from 'eslint-plugin-react-refresh' // ✅ Helps detect invalid Fast Refresh patterns in React + Vite.

// 🧩 Export an array of configuration objects.
// ESLint will apply them from top to bottom.
export default [
  {
    // 🚫 Ignore compiled output and build artifacts.
    ignores: ['dist'],
  },

  // 👇 Spread the recommended rule sets directly into this array.
  // These are equivalent to what you’d put under `"extends"` in old ESLint configs.
  ...js.configs.recommended,                  // ✅ ESLint’s recommended JavaScript rules.
  ...reactHooks.configs['recommended-latest'],// ✅ Recommended rules for React Hooks.
  ...(reactRefresh.configs.vite ?? []),       // ✅ Optional React Refresh (used in Vite projects).

  {
    // 🎯 This block applies specifically to JavaScript and JSX files.
    files: ['**/*.{js,jsx}'],

    // 🌐 Define language and environment options for linting.
    languageOptions: {
      ecmaVersion: 'latest',                  // ✅ Enable modern ECMAScript syntax.
      globals: globals.browser,               // ✅ Recognize browser globals like `window`, `document`, etc.
      parserOptions: {
        ecmaFeatures: { jsx: true },          // ✅ Enable JSX parsing for React components.
        sourceType: 'module',                 // ✅ Allow ES module `import`/`export` syntax.
      },
    },

    // ⚙️ Custom linting rules and overrides.
    rules: {
      // 🚨 Report unused variables — but ignore ones that start with
      // an uppercase letter or underscore (common in React components or constants).
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
]
