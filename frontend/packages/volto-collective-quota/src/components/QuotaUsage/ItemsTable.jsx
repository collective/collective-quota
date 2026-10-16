import React from 'react';
import { Link } from 'react-router-dom';
import { defineMessages, FormattedMessage, useIntl } from 'react-intl';
import { Checkbox, Table } from 'semantic-ui-react';
import FormattedDate from '@plone/volto/components/theme/FormattedDate/FormattedDate';
import { flattenToAppURL } from '@plone/volto/helpers/Url/Url';

const messages = defineMessages({
  cannotDelete: {
    id: 'collective.quota.cannot_delete',
    defaultMessage: 'You cannot delete this item',
  },
  selectAll: {
    id: 'collective.quota.select_all',
    defaultMessage: 'Select all items you can delete',
  },
  select: {
    id: 'collective.quota.select',
    defaultMessage: 'Select {title}',
  },
  bytes: {
    id: 'collective.quota.bytes',
    defaultMessage: '{size} bytes',
  },
});

const ItemsTable = ({ items, selected, onToggle, onToggleAll }) => {
  const intl = useIntl();
  const deletable = items.filter((item) => item.can_delete);
  const allSelected =
    deletable.length > 0 &&
    deletable.every((item) => selected.includes(item['@id']));
  return (
    <Table celled striped compact id="quota-usage-items">
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell collapsing>
            <Checkbox
              id="quota-select-all"
              aria-label={intl.formatMessage(messages.selectAll)}
              checked={allSelected}
              disabled={deletable.length === 0}
              onChange={() => onToggleAll(allSelected ? [] : deletable)}
            />
          </Table.HeaderCell>
          <Table.HeaderCell>
            <FormattedMessage id="Title" defaultMessage="Title" />
          </Table.HeaderCell>
          <Table.HeaderCell>
            <FormattedMessage id="Type" defaultMessage="Type" />
          </Table.HeaderCell>
          <Table.HeaderCell>
            <FormattedMessage
              id="collective.quota.location"
              defaultMessage="Location"
            />
          </Table.HeaderCell>
          <Table.HeaderCell>
            <FormattedMessage
              id="collective.quota.size"
              defaultMessage="Size"
            />
          </Table.HeaderCell>
          <Table.HeaderCell>
            <FormattedMessage
              id="collective.quota.modified"
              defaultMessage="Modified"
            />
          </Table.HeaderCell>
          <Table.HeaderCell collapsing>
            <FormattedMessage
              id="collective.quota.actions"
              defaultMessage="Actions"
            />
          </Table.HeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {items.map((item) => {
          const path = flattenToAppURL(item['@id']);
          return (
            <Table.Row key={item['@id']} data-uid={item.UID}>
              <Table.Cell>
                <Checkbox
                  className="quota-select"
                  aria-label={intl.formatMessage(messages.select, {
                    title: item.title,
                  })}
                  title={
                    item.can_delete
                      ? undefined
                      : intl.formatMessage(messages.cannotDelete)
                  }
                  disabled={!item.can_delete}
                  checked={selected.includes(item['@id'])}
                  onChange={() => onToggle(item)}
                />
              </Table.Cell>
              <Table.Cell>
                <Link to={path}>{item.title}</Link>
              </Table.Cell>
              <Table.Cell>{item.type_title}</Table.Cell>
              <Table.Cell>
                <Link to={flattenToAppURL(item.parent['@id']) || '/'}>
                  {item.parent.title}
                </Link>
              </Table.Cell>
              <Table.Cell
                className="quota-size"
                title={intl.formatMessage(messages.bytes, {
                  size: item.blob_size,
                })}
              >
                {item.blob_size_human}
              </Table.Cell>
              <Table.Cell>
                <FormattedDate date={item.modified} long />
              </Table.Cell>
              <Table.Cell>
                <Link to={`${path}/edit`}>
                  <FormattedMessage id="Edit" defaultMessage="Edit" />
                </Link>
              </Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
};

export default ItemsTable;
