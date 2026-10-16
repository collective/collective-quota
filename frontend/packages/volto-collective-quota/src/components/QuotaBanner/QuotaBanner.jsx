import React from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { defineMessages, useIntl } from 'react-intl';
import { Container, Message } from 'semantic-ui-react';

import './QuotaBanner.css';

const messages = defineMessages({
  review: {
    id: 'collective.quota.review_files',
    defaultMessage: 'Review large files',
  },
});

const LEVELS = ['warning', 'exceeded'];

// Slot `aboveApp`. The backend decides who sees quota data (the `quota`
// expansion is absent otherwise) and computes `level` and `message`.
const QuotaBanner = ({ content }) => {
  const intl = useIntl();
  const token = useSelector((state) => state.userSession?.token);
  const quota = content?.['@components']?.quota;
  if (!token || !quota || !LEVELS.includes(quota.level)) return null;
  const exceeded = quota.level === 'exceeded';
  return (
    <Message
      id="collective-quota-banner"
      className="collective-quota-banner"
      data-level={quota.level}
      warning={!exceeded}
      negative={exceeded}
    >
      <Container>
        <p>{quota.message}</p>
        <Link className="ui button basic small" to="/quota-usage">
          {intl.formatMessage(messages.review)}
        </Link>
      </Container>
    </Message>
  );
};

export default QuotaBanner;
