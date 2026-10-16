import React from 'react';
import { screen } from '@testing-library/react';
import {
  Pluggable,
  PluggablesProvider,
} from '@plone/volto/components/manage/Pluggable';
import UserMenuEntry from './UserMenuEntry';
import { makeStore, renderWith } from '../../test-utils';

const menu = (
  <PluggablesProvider>
    <ul id="menu">
      <Pluggable name="toolbar-user-menu" />
    </ul>
    <UserMenuEntry />
  </PluggablesProvider>
);

const action = { id: 'disk-usage', title: 'Disk usage', url: 'x' };

describe('UserMenuEntry', () => {
  it('is hidden without the disk-usage action', () => {
    const store = makeStore({
      actions: { actions: { user: [{ id: 'logout', title: 'Log out' }] } },
    });
    renderWith(menu, { store });
    expect(screen.queryByText('Disk usage')).not.toBeInTheDocument();
  });

  it('is hidden without actions', () => {
    renderWith(menu, { store: makeStore() });
    expect(document.querySelector('#menu li')).toBeNull();
  });

  it('is hidden without a token', () => {
    const store = makeStore({
      userSession: { token: null },
      actions: { actions: { user: [action] } },
    });
    renderWith(menu, { store });
    expect(screen.queryByText('Disk usage')).not.toBeInTheDocument();
  });

  it('links to the disk usage page', () => {
    const store = makeStore({ actions: { actions: { user: [action] } } });
    renderWith(menu, { store });
    const link = screen.getByText('Disk usage').closest('a');
    expect(link).toHaveAttribute('href', '/quota-usage');
    expect(link.closest('#menu')).not.toBeNull();
  });
});
