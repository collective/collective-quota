import { GET_QUOTA_USAGE, REBUILD_QUOTA } from '../constants/ActionTypes';

export {
  deleteContent as deleteQuotaItems,
  linkIntegrityCheck,
} from '@plone/volto/actions/content/content';

export function getQuotaUsage(limit = 25) {
  return {
    type: GET_QUOTA_USAGE,
    request: { op: 'get', path: `/@quota-usage?limit=${limit}` },
  };
}

export function rebuildQuota() {
  return {
    type: REBUILD_QUOTA,
    request: { op: 'post', path: '/@quota-rebuild' },
  };
}
