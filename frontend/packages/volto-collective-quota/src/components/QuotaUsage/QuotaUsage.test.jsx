import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';
import QuotaUsage, { parseLimit } from './QuotaUsage';
import { idle, makeStore, renderWith, usageData } from '../../test-utils';

vi.mock('@plone/volto/components/manage/Toolbar/Toolbar', () => ({
  default: ({ inner }) => <div id="mock-toolbar">{inner}</div>,
}));
vi.mock('@plone/volto/components/theme/Unauthorized/Unauthorized', () => ({
  default: () => <div id="mock-unauthorized" />,
}));
vi.mock('react-toastify', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

const state = (usage = {}, rebuild = idle) => ({
  quota: { usage: { ...idle, loaded: true, ...usage }, rebuild },
  linkIntegrity: { result: [], loading: false },
});

const render = (
  data,
  { path = '/quota-usage', responses = {}, usage } = {},
) => {
  const store = makeStore(state(usage ?? { data }), {
    GET_QUOTA_USAGE: data,
    LINK_INTEGRITY_CHECK: [],
    ...responses,
  });
  renderWith(<QuotaUsage />, { store, path });
  return store;
};

const types = (store) => store.getActions().map((action) => action.type);

describe('parseLimit', () => {
  it.each([
    ['', 25],
    ['?limit=10', 10],
    ['?limit=100', 100],
    ['?limit=7', 25],
    ['?limit=x', 25],
  ])('%s → %d', (search, limit) => {
    expect(parseLimit(search)).toBe(limit);
  });
});

describe('QuotaUsage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches with the limit from the query string', () => {
    const store = render(usageData(), { path: '/quota-usage?limit=10' });
    expect(store.getActions()[0].request.path).toBe('/@quota-usage?limit=10');
  });

  it('renders the summary, the alert and the rows', () => {
    const { container } = { container: document.body };
    render(usageData());
    expect(screen.getByRole('heading', { name: 'Disk usage' })).toBeTruthy();
    expect(container.querySelector('#quota-usage-total').textContent).toBe(
      '3.0 MB',
    );
    expect(container.querySelector('#quota-usage-hard').textContent).toBe(
      '10.0 MB',
    );
    expect(container.querySelector('#quota-usage-bar')).not.toBeNull();
    expect(
      screen.getByText(/Allow new items, block uploads that add bytes/),
    ).toBeInTheDocument();
    expect(container.querySelector('#quota-usage-alert').textContent).toBe(
      usageData().message,
    );
    expect(screen.getByText('Big file').closest('a')).toHaveAttribute(
      'href',
      '/docs/big',
    );
    expect(screen.getByText('Docs').closest('a')).toHaveAttribute(
      'href',
      '/docs',
    );
    expect(container.querySelector('a[href="/docs/big/edit"]')).not.toBeNull();
    expect(screen.getByText('2.0 MB')).toHaveAttribute(
      'title',
      '2097152 bytes',
    );
    expect(screen.getByText(/Showing the 25 largest items/)).toBeTruthy();
    expect(container.querySelector('#quota-usage-manage')).toBeNull();
  });

  it('shows the no limits note and no bar or alert without limits', () => {
    render(
      usageData({
        soft: 0,
        soft_human: null,
        hard: 0,
        hard_human: null,
        percent: null,
        level: 'ok',
        limits_configured: false,
        message: null,
        policy_hint: null,
      }),
    );
    expect(document.querySelector('#quota-usage-no-limits')).not.toBeNull();
    expect(document.querySelector('#quota-usage-bar')).toBeNull();
    expect(document.querySelector('#quota-usage-alert')).toBeNull();
    expect(document.querySelector('#quota-usage-hard')).toBeNull();
    expect(screen.queryByText(/Policy:/)).toBeNull();
  });

  it('shows dashes for a missing limit', () => {
    render(usageData({ soft: 0, soft_human: null }));
    expect(
      screen.getByText(/Soft limit: – · Hard limit: 10.0 MB/),
    ).toBeTruthy();
  });

  it('shows an empty listing', () => {
    render(usageData({ items: [] }));
    expect(document.querySelector('#quota-usage-empty')).not.toBeNull();
    expect(document.querySelector('#quota-select-all')).toBeNull();
  });

  it('disables the checkbox of items that cannot be deleted', () => {
    render(usageData());
    const row = document.querySelector('[data-uid="uid-small"]');
    expect(row.querySelector('.quota-select')).toHaveClass('disabled');
    const input = row.querySelector('.quota-select input');
    expect(input).toBeDisabled();
    expect(input).toHaveAttribute('title', 'You cannot delete this item');
    expect(
      document
        .querySelector('[data-uid="uid-big"] .quota-select input')
        .getAttribute('title'),
    ).toBeNull();
  });

  it('shows a loader while loading', () => {
    render(null, { usage: { data: null } });
    expect(document.querySelector('.ui.loader')).not.toBeNull();
  });

  it('shows the not installed message on 404', () => {
    render(null, { usage: { data: null, error: { status: 404 } } });
    expect(
      screen.getByText('collective.quota is not installed on the backend.'),
    ).toBeInTheDocument();
  });

  it.each([401, 403])('renders Unauthorized on %d', (status) => {
    render(null, { usage: { data: null, error: { status } } });
    expect(document.querySelector('#mock-unauthorized')).not.toBeNull();
  });

  it('changes the limit', async () => {
    const store = render(usageData());
    fireEvent.click(screen.getByRole('button', { name: '50' }));
    await waitFor(() =>
      expect(store.getActions().at(-1).request.path).toBe(
        '/@quota-usage?limit=50',
      ),
    );
  });

  it('selects all deletable items and unselects them', () => {
    render(usageData());
    const deleteButton = document.querySelector('#quota-delete-selected');
    expect(deleteButton).toBeDisabled();
    fireEvent.click(document.querySelector('#quota-select-all'));
    expect(deleteButton).not.toBeDisabled();
    expect(deleteButton.textContent).toBe('Delete selected (1)');
    fireEvent.click(document.querySelector('#quota-select-all'));
    expect(deleteButton).toBeDisabled();
  });

  it('toggles single items', () => {
    render(usageData());
    const checkbox = document.querySelector('[data-uid="uid-big"] input');
    fireEvent.click(checkbox);
    expect(document.querySelector('#quota-delete-selected').textContent).toBe(
      'Delete selected (1)',
    );
    fireEvent.click(checkbox);
    expect(document.querySelector('#quota-delete-selected')).toBeDisabled();
  });

  const selectAndConfirm = async () => {
    fireEvent.click(document.querySelector('[data-uid="uid-big"] input'));
    fireEvent.click(document.querySelector('#quota-delete-selected'));
    const confirm = await screen.findByRole('button', { name: 'Delete' });
    fireEvent.click(confirm);
  };

  it('deletes the selected items and reports the space freed', async () => {
    const after = usageData({ total: 1024 * 1024 });
    let calls = 0;
    const store = render(usageData(), {
      responses: {
        GET_QUOTA_USAGE: () => (calls++ === 0 ? usageData() : after),
        DELETE_CONTENT: {},
      },
    });
    await waitFor(() => expect(calls).toBe(1));
    await selectAndConfirm();
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    const deletes = store
      .getActions()
      .filter((action) => action.type === 'DELETE_CONTENT');
    expect(deletes.map((action) => action.request.path)).toEqual(['/docs/big']);
    expect(types(store)).toContain('LINK_INTEGRITY_CHECK');
    expect(toast.success.mock.calls[0][0].props.content).toBe(
      'Deleted 1 items, freeing 2.0 MB.',
    );
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('reports items that could not be deleted', async () => {
    render(usageData(), {
      responses: { DELETE_CONTENT: new Error('locked') },
    });
    await selectAndConfirm();
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.error.mock.calls[0][0].props.content).toBe(
      'These items could not be deleted: Big file',
    );
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('keeps the total when the refetch fails', async () => {
    let calls = 0;
    render(usageData(), {
      responses: {
        GET_QUOTA_USAGE: () =>
          calls++ === 0 ? usageData() : new Error('gone'),
        DELETE_CONTENT: {},
      },
    });
    await waitFor(() => expect(calls).toBe(1));
    await selectAndConfirm();
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success.mock.calls[0][0].props.content).toBe(
      'Deleted 1 items, freeing 0 KB.',
    );
  });

  it('cancels the confirmation', async () => {
    const store = render(usageData());
    fireEvent.click(document.querySelector('[data-uid="uid-big"] input'));
    fireEvent.click(document.querySelector('#quota-delete-selected'));
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
    expect(types(store)).not.toContain('DELETE_CONTENT');
  });

  it('offers settings and rebuild to managers', async () => {
    const store = render(usageData({ can_manage: true }), {
      responses: {
        REBUILD_QUOTA: { items: 12, total: 3, total_human: '1 KB' },
      },
    });
    expect(screen.getByText('Quota settings').closest('a')).toHaveAttribute(
      'href',
      '/controlpanel/collective-quota',
    );
    fireEvent.click(document.querySelector('#quota-rebuild'));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success.mock.calls[0][0].props.content).toBe(
      'Usage data rebuilt: 12 items, 1 KB in total.',
    );
    expect(types(store)).toContain('REBUILD_QUOTA');
  });

  it('reports a failed rebuild', async () => {
    render(usageData({ can_manage: true }), {
      responses: { REBUILD_QUOTA: new Error('no') },
    });
    fireEvent.click(document.querySelector('#quota-rebuild'));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it('has a back button in the toolbar', () => {
    render(usageData());
    expect(document.querySelector('#mock-toolbar a[href="/"]')).not.toBeNull();
  });
});
