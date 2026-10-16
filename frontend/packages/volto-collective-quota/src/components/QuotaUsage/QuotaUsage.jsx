import React, { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useHistory, useLocation } from 'react-router-dom';
import { defineMessages, FormattedMessage, useIntl } from 'react-intl';
import { toast } from 'react-toastify';
import { Button, Container, Loader, Message } from 'semantic-ui-react';
import Helmet from '@plone/volto/helpers/Helmet/Helmet';
import { flattenToAppURL } from '@plone/volto/helpers/Url/Url';
import { useClient } from '@plone/volto/hooks/client/useClient';
import Icon from '@plone/volto/components/theme/Icon/Icon';
import Toast from '@plone/volto/components/manage/Toast/Toast';
import Toolbar from '@plone/volto/components/manage/Toolbar/Toolbar';
import Unauthorized from '@plone/volto/components/theme/Unauthorized/Unauthorized';
import backSVG from '@plone/volto/icons/back.svg';

import {
  deleteQuotaItems,
  getQuotaUsage,
  rebuildQuota,
} from '../../actions/quota';
import { human } from '../../helpers/format';
import DeleteModal from './DeleteModal';
import ItemsTable from './ItemsTable';
import UsageSummary from './UsageSummary';

import './QuotaUsage.css';

const LIMITS = [10, 25, 50, 100];
const DEFAULT_LIMIT = 25;

export const messages = defineMessages({
  title: { id: 'collective.quota.disk_usage', defaultMessage: 'Disk usage' },
  back: { id: 'Back', defaultMessage: 'Back' },
  info: { id: 'Info', defaultMessage: 'Info' },
  error: { id: 'Error', defaultMessage: 'Error' },
  deleted: {
    id: 'collective.quota.deleted',
    defaultMessage: 'Deleted {count} items, freeing {size}.',
  },
  deleteFailed: {
    id: 'collective.quota.delete_failed',
    defaultMessage: 'These items could not be deleted: {titles}',
  },
  rebuilt: {
    id: 'collective.quota.rebuilt',
    defaultMessage: 'Usage data rebuilt: {count} items, {total} in total.',
  },
  rebuildFailed: {
    id: 'collective.quota.rebuild_failed',
    defaultMessage: 'Rebuilding the usage data failed.',
  },
});

export function parseLimit(search) {
  const limit = parseInt(new URLSearchParams(search).get('limit'), 10);
  return LIMITS.includes(limit) ? limit : DEFAULT_LIMIT;
}

/** Rebuild usage data, toast the result and refetch. Shared with the control panel. */
export function useRebuild(refetch) {
  const intl = useIntl();
  const dispatch = useDispatch();
  const rebuilding = useSelector((state) => state.quota.rebuild.loading);
  const rebuild = useCallback(
    () =>
      dispatch(rebuildQuota())
        .then((result) => {
          toast.success(
            <Toast
              success
              title={intl.formatMessage(messages.info)}
              content={intl.formatMessage(messages.rebuilt, {
                count: result.items,
                total: result.total_human,
              })}
            />,
          );
        })
        .catch(() => {
          toast.error(
            <Toast
              error
              title={intl.formatMessage(messages.error)}
              content={intl.formatMessage(messages.rebuildFailed)}
            />,
          );
        })
        .finally(refetch),
    [dispatch, intl, refetch],
  );
  return [rebuild, rebuilding];
}

const QuotaUsage = () => {
  const intl = useIntl();
  const dispatch = useDispatch();
  const history = useHistory();
  const { pathname, search } = useLocation();
  const isClient = useClient();
  const limit = parseLimit(search);
  const usage = useSelector((state) => state.quota.usage);
  const [selected, setSelected] = useState([]);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refetch = useCallback(
    () => dispatch(getQuotaUsage(limit)).catch(() => null),
    [dispatch, limit],
  );
  useEffect(() => {
    refetch();
  }, [refetch]);
  const [rebuild, rebuilding] = useRebuild(refetch);

  const data = usage.data;
  const items = data?.items ?? [];
  const selectedItems = items.filter((item) => selected.includes(item['@id']));

  const toggle = (item) =>
    setSelected((ids) =>
      ids.includes(item['@id'])
        ? ids.filter((id) => id !== item['@id'])
        : [...ids, item['@id']],
    );

  const onDelete = async () => {
    setConfirming(false);
    setDeleting(true);
    const before = data.total;
    const failed = [];
    let count = 0;
    // One request per item, so one failure (e.g. a lock) does not stop the rest.
    for (const item of selectedItems) {
      try {
        await dispatch(deleteQuotaItems(flattenToAppURL(item['@id'])));
        count += 1;
      } catch (e) {
        failed.push(item.title);
      }
    }
    const after = await refetch();
    setSelected([]);
    setDeleting(false);
    if (count > 0) {
      toast.success(
        <Toast
          success
          title={intl.formatMessage(messages.info)}
          content={intl.formatMessage(messages.deleted, {
            count,
            size: human(before - (after?.total ?? before)),
          })}
        />,
      );
    }
    if (failed.length > 0) {
      toast.error(
        <Toast
          error
          title={intl.formatMessage(messages.error)}
          content={intl.formatMessage(messages.deleteFailed, {
            titles: failed.join(', '),
          })}
        />,
      );
    }
  };

  const status = usage.error?.status;
  if (status === 401 || status === 403) return <Unauthorized />;

  return (
    <div id="page-quota-usage">
      <Helmet title={intl.formatMessage(messages.title)} />
      <Container>
        <h1>{intl.formatMessage(messages.title)}</h1>
        {status === 404 && (
          <Message warning id="quota-usage-not-installed">
            <FormattedMessage
              id="collective.quota.not_installed"
              defaultMessage="collective.quota is not installed on the backend."
            />
          </Message>
        )}
        {!data && !usage.error && <Loader active inline="centered" />}
        {data && (
          <>
            <UsageSummary
              usage={data}
              showSettings
              onRebuild={rebuild}
              rebuilding={rebuilding}
            />
            {data.level !== 'ok' && data.message && (
              <Message
                id="quota-usage-alert"
                warning={data.level === 'warning'}
                negative={data.level === 'exceeded'}
              >
                {data.message}
              </Message>
            )}
            <div className="collective-quota-toolbar">
              <div>
                <FormattedMessage
                  id="collective.quota.show"
                  defaultMessage="Show"
                />{' '}
                <Button.Group size="small" id="quota-usage-limits">
                  {LIMITS.map((value) => (
                    <Button
                      key={value}
                      active={value === limit}
                      onClick={() => {
                        setSelected([]);
                        history.push(`${pathname}?limit=${value}`);
                      }}
                    >
                      {value}
                    </Button>
                  ))}
                </Button.Group>
              </div>
              <Button
                id="quota-delete-selected"
                negative
                size="small"
                disabled={selectedItems.length === 0 || deleting}
                loading={deleting}
                onClick={() => setConfirming(true)}
              >
                <FormattedMessage
                  id="collective.quota.delete_selected"
                  defaultMessage="Delete selected ({count})"
                  values={{ count: selectedItems.length }}
                />
              </Button>
            </div>
            {items.length > 0 ? (
              <ItemsTable
                items={items}
                selected={selected}
                onToggle={toggle}
                onToggleAll={(rows) => setSelected(rows.map((r) => r['@id']))}
              />
            ) : (
              <p id="quota-usage-empty">
                <FormattedMessage
                  id="collective.quota.empty"
                  defaultMessage="No uploaded files or images found."
                />
              </p>
            )}
            <p className="discreet">
              <FormattedMessage
                id="collective.quota.footer"
                defaultMessage="Sizes include only uploaded files and images. Showing the {limit} largest items you can see."
                values={{ limit: data.limit }}
              />
            </p>
            <DeleteModal
              open={confirming}
              items={selectedItems}
              onCancel={() => setConfirming(false)}
              onOk={onDelete}
            />
          </>
        )}
      </Container>
      {isClient &&
        createPortal(
          <Toolbar
            pathname={pathname}
            hideDefaultViewButtons
            inner={
              <Link to="/" className="item">
                <Icon
                  name={backSVG}
                  className="contents circled"
                  size="30px"
                  title={intl.formatMessage(messages.back)}
                />
              </Link>
            }
          />,
          document.getElementById('toolbar'),
        )}
    </div>
  );
};

export default QuotaUsage;
