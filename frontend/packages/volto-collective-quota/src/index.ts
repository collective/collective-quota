import type { ConfigType } from '@plone/registry';
import serverSVG from '@plone/volto/icons/server.svg';
import installSettings from './config/settings';
import QuotaBanner from './components/QuotaBanner/QuotaBanner';
import UserMenuEntry from './components/UserMenuEntry/UserMenuEntry';
import QuotaUsage from './components/QuotaUsage/QuotaUsage';
import QuotaControlpanel from './components/QuotaControlpanel/QuotaControlpanel';
import quotaReducer from './reducers/quota';
import { notOnRoutes } from './helpers/predicates';

function applyConfig(config: ConfigType) {
  installSettings(config);

  // Banner data on every content request Volto already makes.
  config.settings.apiExpanders = [
    ...config.settings.apiExpanders,
    { match: '', GET_CONTENT: ['quota'] },
  ];

  // Banner above everything, except on the pages that show the summary.
  config.registerSlotComponent({
    slot: 'aboveApp',
    name: 'collective-quota-banner',
    component: QuotaBanner,
    predicates: [
      notOnRoutes(['/quota-usage', '/controlpanel/collective-quota']),
    ],
  });

  // "Disk usage" in the personal tools menu.
  config.settings.appExtras = [
    ...config.settings.appExtras,
    { match: '', component: UserMenuEntry, props: {} },
  ];

  // Add-on routes come before Volto's `/controlpanel/:id`.
  config.addonRoutes = [
    ...config.addonRoutes,
    { path: '/quota-usage', component: QuotaUsage, exact: true },
    {
      path: '/controlpanel/collective-quota',
      component: QuotaControlpanel,
      exact: true,
    },
  ];
  config.settings.nonContentRoutes = [
    ...config.settings.nonContentRoutes,
    /\/quota-usage$/,
  ];

  config.addonReducers = { ...config.addonReducers, quota: quotaReducer };

  config.settings.controlPanelsIcons = {
    ...config.settings.controlPanelsIcons,
    'collective-quota': serverSVG,
  };

  return config;
}

export default applyConfig;
