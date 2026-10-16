import React from 'react';
import configureStore from 'redux-mock-store';
import { Provider } from 'react-intl-redux';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';

/**
 * Mock store whose dispatch of a request action returns a promise, like
 * Volto's api middleware: ``responses[type]`` is the result (a function gets
 * the action), an ``Error`` rejects.
 */
export function makeStore(state, responses = {}) {
  const api = () => (next) => (action) => {
    next(action);
    if (!action.request) return action;
    const response = responses[action.type];
    const result = typeof response === 'function' ? response(action) : response;
    return result instanceof Error
      ? Promise.reject(result)
      : Promise.resolve(result);
  };
  return configureStore([api])({
    intl: { locale: 'en', messages: {} },
    userSession: { token: 'token' },
    ...state,
  });
}

export function renderWith(ui, { store, path = '/' }) {
  const toolbar = document.createElement('div');
  toolbar.id = 'toolbar';
  document.body.appendChild(toolbar);
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </Provider>,
  );
}

export const usageData = (overrides = {}) => ({
  '@id': 'http://localhost:3000/@quota-usage',
  total: 3 * 1024 * 1024,
  total_human: '3.0 MB',
  soft: 2 * 1024 * 1024,
  soft_human: '2.0 MB',
  hard: 10 * 1024 * 1024,
  hard_human: '10.0 MB',
  percent: 30,
  level: 'warning',
  limits_configured: true,
  message: 'Disk usage warning: this site uses 3.0 MB of 10.0 MB (30%).',
  policy: 'block_files',
  policy_title: 'Allow new items, block uploads that add bytes',
  policy_hint: 'Uploads are blocked until files are removed.',
  can_manage: false,
  limit: 25,
  limits: [10, 25, 50, 100],
  items: [
    {
      '@id': 'http://localhost:3000/docs/big',
      UID: 'uid-big',
      title: 'Big file',
      '@type': 'File',
      type_title: 'File',
      parent: { '@id': 'http://localhost:3000/docs', title: 'Docs' },
      blob_size: 2 * 1024 * 1024,
      blob_size_human: '2.0 MB',
      modified: '2026-10-16T14:02:11+00:00',
      can_delete: true,
    },
    {
      '@id': 'http://localhost:3000/small',
      UID: 'uid-small',
      title: 'Small image',
      '@type': 'Image',
      type_title: 'Image',
      parent: { '@id': 'http://localhost:3000', title: 'Site' },
      blob_size: 1024 * 1024,
      blob_size_human: '1.0 MB',
      modified: '2026-10-15T10:00:00+00:00',
      can_delete: false,
    },
  ],
  ...overrides,
});

export const idle = { loading: false, loaded: false, error: null, data: null };
