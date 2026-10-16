import { getQuotaUsage, rebuildQuota, deleteQuotaItems } from './quota';

describe('quota actions', () => {
  it('getQuotaUsage', () => {
    expect(getQuotaUsage()).toEqual({
      type: 'GET_QUOTA_USAGE',
      request: { op: 'get', path: '/@quota-usage?limit=25' },
    });
    expect(getQuotaUsage(10).request.path).toBe('/@quota-usage?limit=10');
  });

  it('rebuildQuota', () => {
    expect(rebuildQuota()).toEqual({
      type: 'REBUILD_QUOTA',
      request: { op: 'post', path: '/@quota-rebuild' },
    });
  });

  it('deleteQuotaItems is Volto deleteContent', () => {
    expect(deleteQuotaItems('/a')).toEqual({
      type: 'DELETE_CONTENT',
      mode: 'serial',
      request: { op: 'del', path: '/a' },
    });
  });
});
