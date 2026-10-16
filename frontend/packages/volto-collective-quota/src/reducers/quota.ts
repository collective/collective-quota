import { GET_QUOTA_USAGE, REBUILD_QUOTA } from '../constants/ActionTypes';

type RequestState = {
  loading: boolean;
  loaded: boolean;
  error: { status?: number; message?: string } | null;
  data: any;
};

export type QuotaState = {
  usage: RequestState;
  rebuild: RequestState;
};

const idle: RequestState = {
  loading: false,
  loaded: false,
  error: null,
  data: null,
};

const initialState: QuotaState = { usage: idle, rebuild: idle };

const KEYS: Record<string, keyof QuotaState> = {
  [GET_QUOTA_USAGE]: 'usage',
  [REBUILD_QUOTA]: 'rebuild',
};

function errorOf(action: any) {
  const error = action.error || {};
  return {
    status: error.status ?? error.response?.status,
    message: error.response?.body?.message ?? error.message,
  };
}

export default function quota(
  state: QuotaState = initialState,
  action: any = {},
): QuotaState {
  const match = /^(.*)_(PENDING|SUCCESS|FAIL)$/.exec(action.type || '');
  const key = match && KEYS[match[1]];
  if (!key) return state;
  switch (match[2]) {
    case 'PENDING':
      return {
        ...state,
        [key]: { ...state[key], loading: true, loaded: false, error: null },
      };
    case 'SUCCESS':
      return {
        ...state,
        [key]: {
          loading: false,
          loaded: true,
          error: null,
          data: action.result,
        },
      };
    default:
      return {
        ...state,
        [key]: {
          loading: false,
          loaded: false,
          error: errorOf(action),
          data: null,
        },
      };
  }
}
