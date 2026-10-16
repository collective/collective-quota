import React, { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { defineMessages, FormattedMessage, useIntl } from 'react-intl';
import { Confirm, Dimmer, Loader, Table } from 'semantic-ui-react';
import { linkIntegrityCheck } from '@plone/volto/actions/content/content';
import { flattenToAppURL } from '@plone/volto/helpers/Url/Url';

export const MAX_BREACHES = 10;

// Same message ids as Volto's ContentsDeleteModal, so its translations apply.
const messages = defineMessages({
  deleteConfirmSingleItem: {
    id: 'Delete this item?',
    defaultMessage: 'Delete this item?',
  },
  deleteConfirmMultipleItems: {
    id: 'Delete selected items?',
    defaultMessage: 'Delete selected items?',
  },
  loading: {
    id: 'link-integrity: loading references',
    defaultMessage: 'Checking references...',
  },
  delete: { id: 'Delete', defaultMessage: 'Delete' },
  deleteAndBreak: {
    id: 'link-integrity: Delete item and break links',
    defaultMessage: 'Delete item and break links',
  },
  cancel: { id: 'Cancel', defaultMessage: 'Cancel' },
  item: { id: 'item', defaultMessage: 'item' },
  items: { id: 'items', defaultMessage: 'items' },
  reference: { id: 'reference', defaultMessage: 'reference' },
  references: { id: 'references', defaultMessage: 'references' },
  folderDeletionSingle: {
    id: 'This item contains subitems. Deleting it will also delete its {containedItemsToDelete} {variation} inside.',
    defaultMessage:
      'This item contains subitems. Deleting it will also delete its {containedItemsToDelete} {variation} inside.',
  },
  folderDeletionMultiple: {
    id: 'Some items contain subitems. Deleting them will also delete their {containedItemsToDelete} {variation} inside.',
    defaultMessage:
      'Some items contain subitems. Deleting them will also delete their {containedItemsToDelete} {variation} inside.',
  },
  brokenReferencesMultiple: {
    id: 'Some items are referenced by other contents. Deleting them will break {brokenReferences} {variation}.',
    defaultMessage:
      'Some items are referenced by other contents. Deleting them will break {brokenReferences} {variation}.',
  },
  brokenReferencesSingle: {
    id: 'Deleting this item will break {brokenReferences} {variation}.',
    defaultMessage:
      'Deleting this item will break {brokenReferences} {variation}.',
  },
});

/**
 * Breaches whose source is not itself being deleted, grouped by source.
 * @returns {{source: Object, targets: Object[]}[]}
 */
export function groupBreaches(results, selectedIds) {
  const bySource = new Map();
  (results || []).forEach((target) => {
    (target.breaches || []).forEach((source) => {
      if (selectedIds.some((id) => source['@id'] === id)) return;
      if (!bySource.has(source.uid)) {
        bySource.set(source.uid, { source, targets: [] });
      }
      bySource.get(source.uid).targets.push(target);
    });
  });
  return Array.from(bySource.values());
}

const DeleteModal = ({ open, items, onCancel, onOk }) => {
  const intl = useIntl();
  const dispatch = useDispatch();
  const results = useSelector((state) => state.linkIntegrity?.result);
  const loading = useSelector((state) => state.linkIntegrity?.loading);
  const ids = useMemo(() => items.map((item) => item['@id']), [items]);
  const uids = useMemo(() => items.map((item) => item.UID), [items]);

  useEffect(() => {
    if (open && uids.length > 0) dispatch(linkIntegrityCheck(uids));
  }, [open, uids, dispatch]);

  if (!open) return null;

  const breaches = groupBreaches(results, ids);
  const contained = (results || []).reduce(
    (total, result) => total + (result.items_total ?? 0),
    0,
  );
  const multiple = items.length > 1;
  const plural = (count, one, many) =>
    intl.formatMessage(count === 1 ? messages[one] : messages[many]);

  return (
    <Confirm
      open={open}
      className="collective-quota-delete-modal"
      header={intl.formatMessage(
        multiple
          ? messages.deleteConfirmMultipleItems
          : messages.deleteConfirmSingleItem,
      )}
      confirmButton={intl.formatMessage(
        breaches.length > 0 ? messages.deleteAndBreak : messages.delete,
      )}
      cancelButton={intl.formatMessage(messages.cancel)}
      onCancel={onCancel}
      onConfirm={onOk}
      size="small"
      content={
        <div className="content">
          <Dimmer active={!!loading} inverted>
            <Loader indeterminate size="massive">
              {intl.formatMessage(messages.loading)}
            </Loader>
          </Dimmer>
          <ul className="collective-quota-delete-items">
            {items.map((item) => (
              <li key={item['@id']}>
                <Link to={flattenToAppURL(item['@id'])} target="_blank">
                  {item.title}
                </Link>{' '}
                ({item.blob_size_human})
              </li>
            ))}
          </ul>
          {contained > 0 && (
            <p>
              {intl.formatMessage(
                multiple
                  ? messages.folderDeletionMultiple
                  : messages.folderDeletionSingle,
                {
                  containedItemsToDelete: contained,
                  variation: plural(contained, 'item', 'items'),
                },
              )}
            </p>
          )}
          {breaches.length > 0 && (
            <div className="broken-links-list">
              <span className="collective-quota-breaches">
                {intl.formatMessage(
                  multiple
                    ? messages.brokenReferencesMultiple
                    : messages.brokenReferencesSingle,
                  {
                    brokenReferences: breaches.length,
                    variation: plural(
                      breaches.length,
                      'reference',
                      'references',
                    ),
                  },
                )}
              </span>
              <br />
              <FormattedMessage
                id="These items will have broken links"
                defaultMessage="These items will have broken links"
              />
              <Table compact>
                <Table.Body>
                  {breaches
                    .slice(0, MAX_BREACHES)
                    .map(({ source, targets }) => (
                      <Table.Row key={source['@id']} verticalAlign="top">
                        <Table.Cell>
                          <Link to={flattenToAppURL(source['@id'])}>
                            {source.title}
                          </Link>
                        </Table.Cell>
                        <Table.Cell>
                          <FormattedMessage
                            id="refers to"
                            defaultMessage="refers to"
                          />
                          :
                        </Table.Cell>
                        <Table.Cell>
                          <ul style={{ margin: 0 }}>
                            {targets.map((target) => (
                              <li key={target['@id']}>
                                <Link to={flattenToAppURL(target['@id'])}>
                                  {target.title}
                                </Link>
                              </li>
                            ))}
                          </ul>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  {breaches.length > MAX_BREACHES && (
                    <Table.Row>
                      <Table.Cell colSpan="3">
                        <FormattedMessage
                          id="and {count} more…"
                          defaultMessage="and {count} more…"
                          values={{ count: breaches.length - MAX_BREACHES }}
                        />
                      </Table.Cell>
                    </Table.Row>
                  )}
                </Table.Body>
              </Table>
              {!multiple && (
                <Link to={`${flattenToAppURL(items[0]['@id'])}/links-to-item`}>
                  <FormattedMessage
                    id="View links and references to this item"
                    defaultMessage="View links and references to this item"
                  />
                </Link>
              )}
            </div>
          )}
        </div>
      }
    />
  );
};

export default DeleteModal;
