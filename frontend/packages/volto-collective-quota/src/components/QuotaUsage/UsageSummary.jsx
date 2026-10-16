import React from 'react';
import { Link } from 'react-router-dom';
import { defineMessages, FormattedMessage, useIntl } from 'react-intl';
import { Button, Message, Progress, Segment } from 'semantic-ui-react';

const messages = defineMessages({
  settings: {
    id: 'collective.quota.settings',
    defaultMessage: 'Quota settings',
  },
  rebuild: {
    id: 'collective.quota.rebuild',
    defaultMessage: 'Rebuild usage data',
  },
});

const COLORS = { ok: 'green', warning: 'yellow', exceeded: 'red' };

// Usage card shared by the disk usage page and the control panel.
const UsageSummary = ({ usage, showSettings, onRebuild, rebuilding }) => {
  const intl = useIntl();
  return (
    <Segment className="collective-quota-summary" data-level={usage.level}>
      <p>
        {usage.hard ? (
          <FormattedMessage
            id="collective.quota.total_of_hard"
            defaultMessage="Total: {total} of {hard} ({percent} %)"
            values={{
              total: (
                <strong id="quota-usage-total">{usage.total_human}</strong>
              ),
              hard: <strong id="quota-usage-hard">{usage.hard_human}</strong>,
              percent: usage.percent,
            }}
          />
        ) : (
          <FormattedMessage
            id="collective.quota.total"
            defaultMessage="Total: {total}"
            values={{
              total: (
                <strong id="quota-usage-total">{usage.total_human}</strong>
              ),
            }}
          />
        )}
      </p>
      {usage.hard > 0 && (
        <Progress
          id="quota-usage-bar"
          percent={Math.min(usage.percent, 100)}
          color={COLORS[usage.level]}
          size="small"
        />
      )}
      {usage.limits_configured ? (
        <p className="collective-quota-limits">
          <FormattedMessage
            id="collective.quota.limits"
            defaultMessage="Soft limit: {soft} · Hard limit: {hard} · Policy: {policy}"
            values={{
              soft: usage.soft_human || '–',
              hard: usage.hard_human || '–',
              policy: usage.policy_title,
            }}
          />
        </p>
      ) : (
        <Message info size="small" id="quota-usage-no-limits">
          <FormattedMessage
            id="collective.quota.no_limits"
            defaultMessage="No limits are configured. Only the listing below is available."
          />
        </Message>
      )}
      {usage.can_manage && (showSettings || onRebuild) && (
        <div className="collective-quota-manage" id="quota-usage-manage">
          {showSettings && (
            <Button
              as={Link}
              basic
              size="small"
              to="/controlpanel/collective-quota"
            >
              {intl.formatMessage(messages.settings)}
            </Button>
          )}
          {onRebuild && (
            <Button
              id="quota-rebuild"
              basic
              size="small"
              onClick={onRebuild}
              loading={rebuilding}
              disabled={rebuilding}
            >
              {intl.formatMessage(messages.rebuild)}
            </Button>
          )}
        </div>
      )}
    </Segment>
  );
};

export default UsageSummary;
