import quota from './quota';
import { GET_QUOTA_USAGE, REBUILD_QUOTA } from '../constants/ActionTypes';

const idle = { loading: false, loaded: false, error: null, data: null };

describe('quota reducer', () => {
  it('has an initial state', () => {
    expect(quota(undefined, { type: '@@INIT' })).toEqual({
      usage: idle,
      rebuild: idle,
    });
    expect(quota()).toEqual({ usage: idle, rebuild: idle });
  });

  it('ignores unrelated actions', () => {
    const state = quota();
    expect(quota(state, { type: 'GET_CONTENT_SUCCESS' })).toBe(state);
  });

  it('handles pending, success and failure', () => {
    let state = quota(undefined, { type: `${GET_QUOTA_USAGE}_PENDING` });
    expect(state.usage).toEqual({ ...idle, loading: true });
    state = quota(state, {
      type: `${GET_QUOTA_USAGE}_SUCCESS`,
      result: { total: 1 },
    });
    expect(state.usage).toEqual({
      loading: false,
      loaded: true,
      error: null,
      data: { total: 1 },
    });
    state = quota(state, {
      type: `${GET_QUOTA_USAGE}_FAIL`,
      error: { status: 404, response: { body: { message: 'Not found' } } },
    });
    expect(state.usage).toEqual({
      loading: false,
      loaded: false,
      error: { status: 404, message: 'Not found' },
      data: null,
    });
    expect(state.rebuild).toEqual(idle);
  });

  it('keeps the status from the response', () => {
    const state = quota(undefined, {
      type: `${REBUILD_QUOTA}_FAIL`,
      error: { response: { status: 401 }, message: 'Unauthorized' },
    });
    expect(state.rebuild.error).toEqual({
      status: 401,
      message: 'Unauthorized',
    });
  });

  it('copes with a failure without error details', () => {
    const state = quota(undefined, { type: `${REBUILD_QUOTA}_FAIL` });
    expect(state.rebuild.error).toEqual({
      status: undefined,
      message: undefined,
    });
  });
});
