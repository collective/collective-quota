import { defineConfig } from 'vitest/config';
import voltoVitestConfig from '@plone/volto/vitest.config.mjs';
import { createRequire } from 'module';
import path from 'path';

const voltoRoot = path.resolve(__dirname, '../../core/packages/volto');
const voltoRequire = createRequire(path.join(voltoRoot, 'package.json'));

// The add-on declares no runtime dependencies: these come with @plone/volto,
// so resolve them from Volto's own node_modules.
const fromVolto = [
  'react-intl',
  'react-intl-redux',
  'react-redux',
  'react-router',
  'react-router-dom',
  'react-toastify',
  'redux-mock-store',
  'semantic-ui-react',
];

export default defineConfig({
  plugins: voltoVitestConfig.plugins,
  resolve: {
    alias: {
      ...voltoVitestConfig.resolve.alias,
      ...Object.fromEntries(
        fromVolto.map((name) => [
          name,
          path.dirname(voltoRequire.resolve(`${name}/package.json`)),
        ]),
      ),
    },
  },
  test: {
    name: 'volto-collective-quota',
    globals: true,
    environment: 'jsdom',
    isolate: true,
    setupFiles: [
      path.join(voltoRoot, 'test-setup-globals.js'),
      path.join(voltoRoot, 'test-setup-config.jsx'),
      path.join(voltoRoot, 'test-addons-loader.js'),
    ],
    globalSetup: path.join(voltoRoot, 'global-test-setup.js'),
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/**/*.{js,jsx,ts,tsx}'],
      exclude: [
        'src/index.ts',
        'src/config/**',
        'src/test-utils.jsx',
        'src/**/*.test.{js,jsx,ts,tsx}',
      ],
      thresholds: { lines: 90 },
    },
  },
});
