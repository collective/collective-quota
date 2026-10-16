import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useDispatch, useSelector } from 'react-redux';
import { useHistory, useLocation } from 'react-router-dom';
import { defineMessages, useIntl } from 'react-intl';
import { toast } from 'react-toastify';
import { Button, Confirm, Container, Message } from 'semantic-ui-react';
import Helmet from '@plone/volto/helpers/Helmet/Helmet';
import {
  extractInvariantErrors,
  tryParseJSON,
} from '@plone/volto/helpers/FormValidation/FormValidation';
import { useClient } from '@plone/volto/hooks/client/useClient';
import Icon from '@plone/volto/components/theme/Icon/Icon';
import Toast from '@plone/volto/components/manage/Toast/Toast';
import Toolbar from '@plone/volto/components/manage/Toolbar/Toolbar';
import Unauthorized from '@plone/volto/components/theme/Unauthorized/Unauthorized';
import { Form } from '@plone/volto/components/manage/Form';
import {
  getControlpanel,
  updateControlpanel,
} from '@plone/volto/actions/controlpanels/controlpanels';
import config from '@plone/volto/registry';
import saveSVG from '@plone/volto/icons/save.svg';
import clearSVG from '@plone/volto/icons/clear.svg';
import undoSVG from '@plone/volto/icons/undo.svg';

import { getQuotaUsage } from '../../actions/quota';
import UsageSummary from '../QuotaUsage/UsageSummary';
import { useRebuild } from '../QuotaUsage/QuotaUsage';

export const PANEL_ID = 'collective-quota';

const messages = defineMessages({
  changesSaved: { id: 'Changes saved.', defaultMessage: 'Changes saved.' },
  save: { id: 'Save', defaultMessage: 'Save' },
  cancel: { id: 'Cancel', defaultMessage: 'Cancel' },
  info: { id: 'Info', defaultMessage: 'Info' },
  error: { id: 'Error', defaultMessage: 'Error' },
  reset: {
    id: 'collective.quota.reset',
    defaultMessage: 'Reset to defaults',
  },
  resetConfirm: {
    id: 'collective.quota.reset_confirm',
    defaultMessage:
      'Clear every value saved in this control panel? Environment variables or built-in defaults will apply.',
  },
  resetConfirmLocked: {
    id: 'collective.quota.reset_confirm_locked',
    defaultMessage:
      'Locked settings ({fields}) are fixed by the environment and stay as they are.',
  },
  resetDone: {
    id: 'collective.quota.reset_done',
    defaultMessage:
      'Settings reset. Environment variables or built-in defaults apply now.',
  },
  current: {
    id: 'collective.quota.current_value',
    defaultMessage: 'Current value: {value} ({source})',
  },
  sourceRegistry: {
    id: 'collective.quota.source_registry',
    defaultMessage: 'from control panel',
  },
  sourceEnv: {
    id: 'collective.quota.source_env',
    defaultMessage: 'from environment',
  },
  sourceDefault: {
    id: 'collective.quota.source_default',
    defaultMessage: 'default',
  },
  lockedField: {
    id: 'collective.quota.locked_field',
    defaultMessage: 'Locked by environment variable {variable}.',
  },
  lockedMessage: {
    id: 'collective.quota.locked_message',
    defaultMessage:
      'These settings are fixed by environment variables and cannot be changed here: {fields}.',
  },
});

const SOURCES = {
  registry: messages.sourceRegistry,
  env: messages.sourceEnv,
  'env-locked': messages.sourceEnv,
  default: messages.sourceDefault,
};

export const envVariable = (name) => `COLLECTIVE_QUOTA_${name.toUpperCase()}`;

function displayValue(property, value) {
  const choice = (property.choices || []).find(([token]) => token === value);
  return choice ? choice[1] : String(value);
}

/**
 * The control panel schema with provenance in each description; locked
 * fields are disabled (Volto's widgets honour `isDisabled`, not `readonly`).
 */
export function decorateSchema(schema, panel, intl) {
  const locked = panel.locked || [];
  const properties = Object.fromEntries(
    Object.entries(schema.properties).map(([name, property]) => {
      const notes = [];
      if (panel.effective && name in panel.effective) {
        notes.push(
          intl.formatMessage(messages.current, {
            value: displayValue(property, panel.effective[name]),
            source: intl.formatMessage(
              SOURCES[panel.sources?.[name]] || messages.sourceDefault,
            ),
          }),
        );
      }
      const isLocked = locked.includes(name);
      if (isLocked) {
        notes.push(
          intl.formatMessage(messages.lockedField, {
            variable: envVariable(name),
          }),
        );
      }
      const description = [property.description, ...notes]
        .filter(Boolean)
        .join(' ');
      return [
        name,
        isLocked
          ? { ...property, description, isDisabled: true }
          : { ...property, description },
      ];
    }),
  );
  return { ...schema, properties };
}

function errorText(err) {
  const message =
    err?.response?.body?.error?.message ||
    err?.response?.body?.message ||
    err?.response?.text ||
    '';
  return (
    new DOMParser().parseFromString(message, 'text/html')?.all?.[0]
      ?.textContent || message
  );
}

const QuotaControlpanel = () => {
  const intl = useIntl();
  const dispatch = useDispatch();
  const history = useHistory();
  const { pathname } = useLocation();
  const isClient = useClient();
  const formRef = useRef();
  const controlpanel = useSelector((state) => state.controlpanels.controlpanel);
  const updateRequest = useSelector((state) => state.controlpanels.update);
  const usage = useSelector((state) => state.quota.usage.data);
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [confirmReset, setConfirmReset] = useState(false);
  // Remounts the form after a reset, so it shows the new values.
  const [formKey, setFormKey] = useState(0);

  const refetchUsage = useCallback(
    () => dispatch(getQuotaUsage(10)).catch(() => null),
    [dispatch],
  );
  const refetch = useCallback(
    () =>
      Promise.all([
        dispatch(getControlpanel(PANEL_ID)).catch((err) => setLoadError(err)),
        refetchUsage(),
      ]),
    [dispatch, refetchUsage],
  );
  useEffect(() => {
    refetch();
  }, [refetch]);
  const [rebuild, rebuilding] = useRebuild(refetchUsage);

  const panel = controlpanel?.['@id']?.endsWith(`/${PANEL_ID}`)
    ? controlpanel
    : null;
  const locked = panel?.locked || [];

  const onSubmit = (data) => {
    setError(null);
    return dispatch(updateControlpanel(panel['@id'], data))
      .then(() => {
        toast.info(
          <Toast
            info
            title={intl.formatMessage(messages.info)}
            content={intl.formatMessage(messages.changesSaved)}
          />,
        );
        return refetch();
      })
      .catch((err) => {
        const text = errorText(err);
        const errorsList = tryParseJSON(text);
        const invariantErrors = Array.isArray(errorsList)
          ? extractInvariantErrors(errorsList)
          : [];
        setError(text);
        if (invariantErrors.length > 0) {
          toast.error(
            <Toast
              error
              title={intl.formatMessage(messages.error)}
              content={invariantErrors.join(' - ')}
            />,
          );
        }
      });
  };

  const onReset = () => {
    setConfirmReset(false);
    const fields = Object.keys(panel.schema.properties).filter(
      (name) => !locked.includes(name),
    );
    const data = Object.fromEntries(fields.map((name) => [name, null]));
    return dispatch(updateControlpanel(panel['@id'], data))
      .then(() => refetch())
      .then(() => {
        setFormKey((key) => key + 1);
        toast.info(
          <Toast
            info
            title={intl.formatMessage(messages.info)}
            content={intl.formatMessage(messages.resetDone)}
          />,
        );
      })
      .catch((err) => setError(errorText(err)));
  };

  const status = loadError?.status ?? loadError?.response?.status;
  if (status === 401 || status === 403) return <Unauthorized />;
  if (!panel) return <div />;

  const { filterControlPanelsSchema } = config.settings;
  const schema = decorateSchema(filterControlPanelsSchema(panel), panel, intl);

  return (
    <div id="page-controlpanel" className="collective-quota-controlpanel">
      <Helmet title={panel.title} />
      <Container>
        {usage && (
          <UsageSummary
            usage={usage}
            onRebuild={rebuild}
            rebuilding={rebuilding}
          />
        )}
        {locked.length > 0 && (
          <Message info id="quota-locked-message">
            {intl.formatMessage(messages.lockedMessage, {
              fields: locked
                .map((name) => schema.properties[name]?.title || name)
                .join(', '),
            })}
          </Message>
        )}
        <Form
          key={formKey}
          ref={formRef}
          title={panel.title}
          schema={schema}
          formData={panel.data}
          requestError={error}
          onSubmit={onSubmit}
          onCancel={() => history.goBack()}
          hideActions
          loading={updateRequest.loading}
        />
        <Confirm
          open={confirmReset}
          header={intl.formatMessage(messages.reset)}
          content={
            <div className="content">
              <p>{intl.formatMessage(messages.resetConfirm)}</p>
              {locked.length > 0 && (
                <p>
                  {intl.formatMessage(messages.resetConfirmLocked, {
                    fields: locked.join(', '),
                  })}
                </p>
              )}
            </div>
          }
          confirmButton={intl.formatMessage(messages.reset)}
          cancelButton={intl.formatMessage(messages.cancel)}
          onCancel={() => setConfirmReset(false)}
          onConfirm={onReset}
        />
      </Container>
      {isClient &&
        createPortal(
          <Toolbar
            pathname={pathname}
            hideDefaultViewButtons
            inner={
              <>
                <Button
                  id="toolbar-save"
                  className="save"
                  aria-label={intl.formatMessage(messages.save)}
                  onClick={() => formRef.current.onSubmit()}
                  disabled={updateRequest.loading}
                  loading={updateRequest.loading}
                >
                  <Icon
                    name={saveSVG}
                    className="circled"
                    size="30px"
                    title={intl.formatMessage(messages.save)}
                  />
                </Button>
                <Button
                  className="cancel"
                  aria-label={intl.formatMessage(messages.cancel)}
                  onClick={() => history.goBack()}
                >
                  <Icon
                    name={clearSVG}
                    className="circled"
                    size="30px"
                    title={intl.formatMessage(messages.cancel)}
                  />
                </Button>
                <Button
                  id="toolbar-quota-reset"
                  className="reset"
                  aria-label={intl.formatMessage(messages.reset)}
                  onClick={() => setConfirmReset(true)}
                >
                  <Icon
                    name={undoSVG}
                    className="circled"
                    size="30px"
                    title={intl.formatMessage(messages.reset)}
                  />
                </Button>
              </>
            }
          />,
          document.getElementById('toolbar'),
        )}
    </div>
  );
};

export default QuotaControlpanel;
