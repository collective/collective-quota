import React, { forwardRef, useImperativeHandle } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';
import QuotaControlpanel, { envVariable } from './QuotaControlpanel';
import { idle, makeStore, renderWith, usageData } from '../../test-utils';

const submitted = { current: null };

vi.mock('@plone/volto/components/manage/Toolbar/Toolbar', () => ({
  default: ({ inner }) => <div id="mock-toolbar">{inner}</div>,
}));
vi.mock('@plone/volto/components/theme/Unauthorized/Unauthorized', () => ({
  default: () => <div id="mock-unauthorized" />,
}));
vi.mock('react-toastify', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
// Volto's Form needs the whole widget registry; render what we pass instead.
vi.mock('@plone/volto/components/manage/Form', () => ({
  Form: forwardRef(({ schema, formData, onSubmit, requestError }, ref) => {
    useImperativeHandle(ref, () => ({
      onSubmit: () => onSubmit(submitted.current || formData),
    }));
    return (
      <form id="mock-form">
        {requestError && <div id="mock-error">{requestError}</div>}
        {Object.entries(schema.properties).map(([name, property]) => (
          <fieldset key={name} id={`field-${name}`}>
            <label>{property.title}</label>
            <input
              disabled={!!property.isDisabled}
              defaultValue={formData[name] ?? ''}
            />
            <p className="help">{property.description}</p>
          </fieldset>
        ))}
      </form>
    );
  }),
}));

const URL = 'http://localhost:3000/@controlpanels/collective-quota';

const panel = (overrides = {}) => ({
  '@id': URL,
  title: 'Quota',
  group: 'Add-on Configuration',
  schema: {
    fieldsets: [
      {
        id: 'default',
        title: 'Default',
        fields: [
          'soft_limit_mb',
          'hard_limit_mb',
          'over_limit_policy',
          'max_file_size_mb',
        ],
      },
    ],
    properties: {
      soft_limit_mb: { title: 'Soft limit (MB)', description: 'Warn.' },
      hard_limit_mb: { title: 'Hard limit (MB)', description: 'Enforce.' },
      over_limit_policy: {
        title: 'Policy',
        choices: [
          ['block_all', 'Block new items and any upload that adds bytes'],
          ['allow', 'Allow everything, only show warnings'],
        ],
      },
      max_file_size_mb: { title: 'Maximum file size (MB)', description: '' },
    },
    required: [],
  },
  data: {
    soft_limit_mb: 1,
    hard_limit_mb: 50,
    over_limit_policy: null,
    max_file_size_mb: null,
  },
  effective: {
    soft_limit_mb: 1,
    hard_limit_mb: 50,
    over_limit_policy: 'block_all',
    max_file_size_mb: 10,
  },
  sources: {
    soft_limit_mb: 'registry',
    hard_limit_mb: 'env-locked',
    over_limit_policy: 'default',
    max_file_size_mb: 'env',
  },
  locked: ['hard_limit_mb'],
  ...overrides,
});

const render = ({ controlpanel = panel(), responses = {} } = {}) => {
  const store = makeStore(
    {
      controlpanels: { controlpanel, update: { loading: false } },
      quota: {
        usage: { ...idle, loaded: true, data: usageData({ can_manage: true }) },
        rebuild: idle,
      },
    },
    {
      GET_CONTROLPANEL: controlpanel,
      GET_QUOTA_USAGE: usageData({ can_manage: true }),
      UPDATE_CONTROLPANEL: {},
      ...responses,
    },
  );
  renderWith(<QuotaControlpanel />, {
    store,
    path: '/controlpanel/collective-quota',
  });
  return store;
};

const help = (name) =>
  document.querySelector(`#field-${name} .help`).textContent;

describe('QuotaControlpanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    submitted.current = null;
  });

  it('builds environment variable names', () => {
    expect(envVariable('max_file_size_mb')).toBe(
      'COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB',
    );
  });

  it('fetches the panel and the usage', () => {
    const store = render();
    expect(store.getActions().map((a) => a.request.path)).toEqual([
      '/@controlpanels/collective-quota',
      '/@quota-usage?limit=10',
    ]);
  });

  it('shows where each value comes from', () => {
    render();
    expect(help('soft_limit_mb')).toBe(
      'Warn. Current value: 1 (from control panel)',
    );
    expect(help('over_limit_policy')).toBe(
      'Current value: Block new items and any upload that adds bytes (default)',
    );
    expect(help('max_file_size_mb')).toBe(
      'Current value: 10 (from environment)',
    );
  });

  it('disables locked fields and explains the lock', () => {
    render();
    expect(document.querySelector('#field-hard_limit_mb input')).toBeDisabled();
    expect(
      document.querySelector('#field-soft_limit_mb input'),
    ).not.toBeDisabled();
    expect(help('hard_limit_mb')).toBe(
      'Enforce. Current value: 50 (from environment) Locked by environment variable COLLECTIVE_QUOTA_HARD_LIMIT_MB.',
    );
    expect(document.querySelector('#quota-locked-message').textContent).toBe(
      'These settings are fixed by environment variables and cannot be changed here: Hard limit (MB).',
    );
  });

  it('copes with a panel without provenance', () => {
    render({
      controlpanel: panel({
        effective: undefined,
        sources: undefined,
        locked: undefined,
      }),
    });
    expect(help('soft_limit_mb')).toBe('Warn.');
    expect(document.querySelector('#quota-locked-message')).toBeNull();
  });

  it('falls back to "default" for an unknown source', () => {
    render({ controlpanel: panel({ sources: {}, locked: [] }) });
    expect(help('soft_limit_mb')).toBe('Warn. Current value: 1 (default)');
  });

  it('shows the usage segment with the rebuild button', async () => {
    const store = render({
      responses: { REBUILD_QUOTA: { items: 3, total: 1, total_human: '1 KB' } },
    });
    expect(document.querySelector('#quota-usage-total').textContent).toBe(
      '3.0 MB',
    );
    expect(screen.queryByText('Quota settings')).toBeNull();
    fireEvent.click(document.querySelector('#quota-rebuild'));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(store.getActions().map((a) => a.type)).toContain('REBUILD_QUOTA');
  });

  it('renders nothing until its panel is loaded', () => {
    render({
      controlpanel: { '@id': 'http://localhost:3000/@controlpanels/mail' },
    });
    expect(document.querySelector('#mock-form')).toBeNull();
  });

  it.each([401, 403])('renders Unauthorized on %d', async (status) => {
    render({
      controlpanel: null,
      responses: { GET_CONTROLPANEL: Object.assign(new Error(), { status }) },
    });
    expect(
      await screen.findByText('', { selector: '#mock-unauthorized' }),
    ).toBeTruthy();
  });

  it('saves', async () => {
    const store = render();
    submitted.current = { soft_limit_mb: 2 };
    fireEvent.click(document.querySelector('#toolbar-save'));
    await waitFor(() => expect(toast.info).toHaveBeenCalled());
    const update = store
      .getActions()
      .find((a) => a.type === 'UPDATE_CONTROLPANEL');
    expect(update.request).toEqual({
      op: 'patch',
      path: URL,
      data: { soft_limit_mb: 2 },
    });
  });

  it('shows invariant errors from the backend', async () => {
    const error = Object.assign(new Error(), {
      response: {
        body: {
          message: JSON.stringify([
            { message: 'The soft limit cannot be higher than the hard limit.' },
          ]),
        },
      },
    });
    render({ responses: { UPDATE_CONTROLPANEL: error } });
    fireEvent.click(document.querySelector('#toolbar-save'));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.error.mock.calls[0][0].props.content).toBe(
      'The soft limit cannot be higher than the hard limit.',
    );
  });

  it('keeps other save errors on the form', async () => {
    const error = Object.assign(new Error(), {
      response: { text: 'Server exploded' },
    });
    render({ responses: { UPDATE_CONTROLPANEL: error } });
    fireEvent.click(document.querySelector('#toolbar-save'));
    expect(await screen.findByText('Server exploded')).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('copes with an empty error', async () => {
    render({ responses: { UPDATE_CONTROLPANEL: new Error() } });
    fireEvent.click(document.querySelector('#toolbar-save'));
    await waitFor(() =>
      expect(document.querySelector('#mock-error')).toBeNull(),
    );
    expect(toast.info).not.toHaveBeenCalled();
  });

  it('resets every field that is not locked', async () => {
    const store = render();
    fireEvent.click(document.querySelector('#toolbar-quota-reset'));
    expect(
      screen.getByText(
        'Locked settings (hard_limit_mb) are fixed by the environment and stay as they are.',
      ),
    ).toBeInTheDocument();
    const dialog = document.querySelector('.ui.modal');
    fireEvent.click(
      Array.from(dialog.querySelectorAll('button')).find(
        (b) => b.textContent === 'Reset to defaults',
      ),
    );
    await waitFor(() => expect(toast.info).toHaveBeenCalled());
    const update = store
      .getActions()
      .find((a) => a.type === 'UPDATE_CONTROLPANEL');
    expect(update.request.data).toEqual({
      soft_limit_mb: null,
      over_limit_policy: null,
      max_file_size_mb: null,
    });
    expect(toast.info.mock.calls[0][0].props.content).toBe(
      'Settings reset. Environment variables or built-in defaults apply now.',
    );
  });

  it('resets everything without locks and can be cancelled', async () => {
    const store = render({ controlpanel: panel({ locked: [] }) });
    fireEvent.click(document.querySelector('#toolbar-quota-reset'));
    expect(screen.queryByText(/Locked settings/)).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: 'Cancel' }).at(-1));
    expect(
      store.getActions().find((a) => a.type === 'UPDATE_CONTROLPANEL'),
    ).toBeUndefined();
  });

  it('shows a failed reset on the form', async () => {
    const error = Object.assign(new Error(), {
      response: { body: { error: { message: 'Nope' } } },
    });
    render({ responses: { UPDATE_CONTROLPANEL: error } });
    fireEvent.click(document.querySelector('#toolbar-quota-reset'));
    fireEvent.click(
      Array.from(document.querySelectorAll('.ui.modal button')).find(
        (b) => b.textContent === 'Reset to defaults',
      ),
    );
    expect(await screen.findByText('Nope')).toBeInTheDocument();
  });

  it('cancels with the toolbar', () => {
    render();
    fireEvent.click(document.querySelector('#mock-toolbar .cancel'));
  });
});
