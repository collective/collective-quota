import React from 'react';
import { screen } from '@testing-library/react';
import DeleteModal, { groupBreaches, MAX_BREACHES } from './DeleteModal';
import { makeStore, renderWith, usageData } from '../../test-utils';

const [big, small] = usageData().items;
const doc = (n) => ({
  '@id': `http://localhost:3000/doc-${n}`,
  uid: `doc-${n}`,
  title: `Document ${n}`,
});

const render = (items, result, extra = {}) => {
  const store = makeStore(
    { linkIntegrity: { result, loading: false, ...extra } },
    { LINK_INTEGRITY_CHECK: result },
  );
  renderWith(
    <DeleteModal open items={items} onCancel={() => {}} onOk={() => {}} />,
    { store },
  );
  return store;
};

describe('groupBreaches', () => {
  it('drops breaches from items being deleted and groups by source', () => {
    const results = [
      { ...big, breaches: [doc(1), { ...small, uid: 'uid-small' }] },
      { ...small, breaches: [doc(1)] },
    ];
    const grouped = groupBreaches(results, [big['@id'], small['@id']]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].source.title).toBe('Document 1');
    expect(grouped[0].targets.map((t) => t.title)).toEqual([
      'Big file',
      'Small image',
    ]);
  });

  it('copes with missing results', () => {
    expect(groupBreaches(undefined, [])).toEqual([]);
    expect(groupBreaches([{ '@id': 'x' }], [])).toEqual([]);
  });
});

describe('DeleteModal', () => {
  it('renders nothing when closed', () => {
    const store = makeStore({ linkIntegrity: {} });
    const { container } = renderWith(
      <DeleteModal
        open={false}
        items={[big]}
        onCancel={() => {}}
        onOk={() => {}}
      />,
      { store },
    );
    expect(container).toBeEmptyDOMElement();
    expect(store.getActions()).toEqual([]);
  });

  it('checks link integrity and offers a plain delete', () => {
    const store = render([big], [{ ...big, breaches: [], items_total: 0 }]);
    expect(store.getActions()[0].request.path).toBe(
      '@linkintegrity?uids=uid-big',
    );
    expect(screen.getByText('Delete this item?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.getByText('Big file')).toBeInTheDocument();
    expect(screen.queryByText(/will break/)).toBeNull();
  });

  it('switches the confirm label when links break', () => {
    render([big], [{ ...big, breaches: [doc(1)], items_total: 0 }]);
    expect(
      screen.getByRole('button', { name: 'Delete item and break links' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Deleting this item will break 1 reference.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Document 1').closest('a')).toHaveAttribute(
      'href',
      '/doc-1',
    );
    expect(
      screen.getByText('View links and references to this item').closest('a'),
    ).toHaveAttribute('href', '/docs/big/links-to-item');
  });

  it('lists at most MAX_BREACHES sources, then a count', () => {
    const breaches = Array.from({ length: MAX_BREACHES + 2 }, (_, n) => doc(n));
    const items = [big, { ...small, can_delete: true }];
    render(items, [{ ...big, breaches, items_total: 3 }]);
    expect(screen.getByText('Delete selected items?')).toBeInTheDocument();
    expect(
      screen.getByText(
        `Some items are referenced by other contents. Deleting them will break ${MAX_BREACHES + 2} references.`,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('and 2 more…')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Some items contain subitems. Deleting them will also delete their 3 items inside.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('View links and references to this item'),
    ).toBeNull();
  });

  it('mentions contained items of a single folder', () => {
    render([big], [{ ...big, breaches: [], items_total: 1 }]);
    expect(
      screen.getByText(
        'This item contains subitems. Deleting it will also delete its 1 item inside.',
      ),
    ).toBeInTheDocument();
  });

  it('copes with results without items_total', () => {
    render([big], [{ ...big, breaches: [] }]);
    expect(screen.queryByText(/subitems/)).toBeNull();
  });

  it('shows a loader while checking', () => {
    render([big], undefined, { loading: true });
    expect(screen.getByText('Checking references...')).toBeInTheDocument();
  });
});
