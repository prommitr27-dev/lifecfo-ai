// Typed client for the LifeCFO HTTP API (lifecfo/api/app.py).
// Money arrives as integer satang in fields ending in `_satang`.

export type OpResult = {
  ok: boolean;
  code: string;
  message: string;
  data: Record<string, unknown>;
};

export type Summary = {
  as_of: string;
  total_cash_satang: number;
  pending_decisions: number;
  ai_mode: 'llm' | 'offline';
};

export type CashFlow = {
  hypothetical: boolean;
  as_of: string;
  status: 'FEASIBLE' | 'PLAN_INFEASIBLE' | 'ESSENTIAL_SHORTFALL';
  first_shortfall_on: string | null;
  max_shortfall_satang: number;
  needs_reserves: boolean;
  essential_shortfall_on: string | null;
  essential_shortfall_satang: number;
  total_cash_satang: number;
  min_unallocated_satang: number;
  min_unallocated_on: string | null;
  closing_envelopes_satang: number;
  days: { on: string; unallocated_satang: number; total_cash_satang: number }[];
  months: {
    month: string;
    income: number;
    essential: number;
    debt_minimum: number;
    flexible: number;
    transfers: number;
    extra_debt: number;
    closing_unallocated: number;
    closing_total_cash: number;
  }[];
  events: { on: string; kind: string; name: string; amount_satang: number }[];
};

export type PlanGoal = {
  id: string;
  name: string;
  target_satang: number;
  saved_now_satang: number;
  projected_saved_satang: number;
  completion_month: string | null;
  deadline: string | null;
  on_track: boolean | null;
  shortfall_at_deadline_satang: number;
};

export type PlanSummary = {
  strategy: string;
  label: string;
  horizon_months: number;
  reserve: {
    target_satang: number;
    saved_now_satang: number;
    projected_saved_satang: number;
    reached_month: string | null;
  } | null;
  goals: PlanGoal[];
  first_month: {
    month: string;
    contributions_satang: Record<string, number>;
    extra_debt_satang: Record<string, number>;
    flexible_total_satang: number;
    flexible_max_satang: number;
  };
  months_below_buffer: string[];
  goals_at_risk: string[];
};

export type Plans = {
  hypothetical: boolean;
  status: 'OK' | 'ESSENTIAL_SHORTFALL' | 'REQUIRES_RESERVE_DRAWDOWN' | 'FLEXIBLE_SPENDING_CONSTRAINT';
  position_text: string | null;
  essential_shortfall_on: string | null;
  essential_shortfall_satang: number;
  identical_notes: string[];
  plans: PlanSummary[];
};

export type Sandbox = {
  as_of: string;
  total_cash_satang: number;
  emergency_balance_satang: number;
  audit_intact: boolean;
  pending: { plan_id: string; label: string; strategy: string; created_at: string }[];
  ready: { approval_id: string; plan_id: string; label: string; decided_at: string }[];
  transactions: {
    id: number;
    on: string;
    kind: string;
    ref: string;
    from: string | null;
    to: string | null;
    amount_satang: number;
  }[];
  audit: {
    seq: number;
    ts: string;
    actor: string;
    action: string;
    code: string;
    plan_id: string;
    hash: string;
  }[];
};

export type ChatTurn = { role: 'user' | 'assistant'; text: string };

export type ChatReply = {
  text: string;
  mode: 'offline' | 'llm';
  provider: string;
  model: string;
  notice: string | null;
  tools: { name: string; tier: string | null; ok: boolean }[];
};

export type Streak = {
  count: number;
  best: number;
  status: 'NOT_STARTED' | 'ACTIVE' | 'PROTECTED' | 'PAUSED' | 'BROKEN';
  last_earned: string | null;
  protected_until: string | null;
};

export type Rewards = {
  opted_in: boolean;
  today: string;
  goal_progress: { goal: string; saved: number; target: number; percent: number }[];
  note: string;
  xp?: number;
  level?: number;
  next_level_at_xp?: number | null;
  streaks?: Record<'DAILY' | 'WEEKLY', Streak>;
  missions?: { mode: string; items: { id: string; title: string; done: boolean }[]; note?: string };
  badges?: string[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export type Connection = { baseUrl: string; token: string };

export function createClient({ baseUrl, token }: Connection) {
  const root = baseUrl.replace(/\/+$/, '');

  async function call<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (init?.body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;
    let response: Response;
    try {
      response = await fetch(`${root}${path}`, {
        method: init?.method ?? 'GET',
        headers,
        body: init?.body === undefined ? undefined : JSON.stringify(init.body),
      });
    } catch {
      throw new ApiError(`Cannot reach the server at ${root}. Check the address in Settings.`, 0);
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch {
        // keep statusText
      }
      throw new ApiError(detail || `HTTP ${response.status}`, response.status);
    }
    return (await response.json()) as T;
  }

  const qs = (params: Record<string, number>) =>
    '?' + Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

  return {
    health: () => call<{ ok: boolean; auth_required: boolean }>('/health'),
    summary: () => call<Summary>('/summary'),
    cashflow: (horizonDays: number, incomeChange: number) =>
      call<CashFlow>('/cashflow' + qs({ horizon_days: horizonDays, income_change: incomeChange })),
    plans: (horizonMonths: number, incomeChange: number) =>
      call<Plans>('/plans' + qs({ horizon_months: horizonMonths, income_change: incomeChange })),
    propose: (strategy: string, horizonMonths: number) =>
      call<OpResult>('/plans/propose', {
        method: 'POST',
        body: { strategy, horizon_months: horizonMonths },
      }),
    sandbox: () => call<Sandbox>('/sandbox'),
    decide: (planId: string, approve: boolean) =>
      call<OpResult>(`/sandbox/plans/${encodeURIComponent(planId)}/decision`, {
        method: 'POST',
        body: { approve },
      }),
    execute: (approvalId: string) =>
      call<OpResult>(`/sandbox/approvals/${encodeURIComponent(approvalId)}/execute`, {
        method: 'POST',
      }),
    confirmExpense: (name: string, amountThb: number) =>
      call<OpResult>('/sandbox/expenses', { method: 'POST', body: { name, amount_thb: amountThb } }),
    withdrawReserve: (amountThb: number) =>
      call<OpResult>('/sandbox/reserve/withdraw', {
        method: 'POST',
        body: { amount_thb: amountThb },
      }),
    advance: (days: number) => call<OpResult>('/sandbox/advance', { method: 'POST', body: { days } }),
    reset: () => call<OpResult>('/sandbox/reset', { method: 'POST' }),
    chat: (message: string, history: ChatTurn[], incomeChange: number) =>
      call<ChatReply>('/chat', {
        method: 'POST',
        body: { message, history: history.slice(-20), income_change: incomeChange },
      }),
    rewards: () => call<Rewards>('/rewards'),
    setOptIn: (optedIn: boolean) =>
      call<Rewards>('/rewards/opt-in', { method: 'POST', body: { opted_in: optedIn } }),
    recordReview: () =>
      call<{ recorded: boolean; status: Rewards }>('/rewards/review', { method: 'POST' }),
    pauseStreaks: () => call<Rewards>('/rewards/pause', { method: 'POST' }),
    resumeStreaks: () => call<Rewards>('/rewards/resume', { method: 'POST' }),
  };
}

export type Client = ReturnType<typeof createClient>;
