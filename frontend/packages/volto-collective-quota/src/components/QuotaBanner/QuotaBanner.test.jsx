import React from 'react';
import { screen } from '@testing-library/react';
import QuotaBanner from './QuotaBanner';
import { makeStore, renderWith } from '../../test-utils';

const content = (quota) => ({
  '@id': 'http://localhost:3000/folder',
  '@components': quota ? { quota } : {},
});

const warning = {
  '@id': 'http://localhost:3000/@quota-usage',
  level: 'warning',
  message: 'Disk usage warning: this site uses 3.0 MB of 10.0 MB (30%).',
};

describe('QuotaBanner', () => {
  it('renders nothing without a token', () => {
    const store = makeStore({ userSession: { token: null } });
    const { container } = renderWith(
      <QuotaBanner content={content(warning)} />,
      { store },
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing without the quota expansion', () => {
    const { container } = renderWith(<QuotaBanner content={content()} />, {
      store: makeStore(),
    });
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing without content', () => {
    const { container } = renderWith(<QuotaBanner />, { store: makeStore() });
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for level ok', () => {
    const { container } = renderWith(
      <QuotaBanner content={content({ ...warning, level: 'ok' })} />,
      { store: makeStore() },
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a warning with the backend message and the link', () => {
    const { container } = renderWith(
      <QuotaBanner content={content(warning)} />,
      { store: makeStore() },
    );
    const banner = container.querySelector('#collective-quota-banner');
    expect(banner).toHaveAttribute('data-level', 'warning');
    expect(banner).toHaveClass('warning');
    expect(screen.getByText(warning.message)).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/quota-usage');
  });

  it('renders a negative message when exceeded', () => {
    const { container } = renderWith(
      <QuotaBanner content={content({ ...warning, level: 'exceeded' })} />,
      { store: makeStore() },
    );
    const banner = container.querySelector('#collective-quota-banner');
    expect(banner).toHaveAttribute('data-level', 'exceeded');
    expect(banner).toHaveClass('negative');
  });
});
