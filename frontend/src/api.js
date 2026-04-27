// Dev: direct to localhost:8000 (CORS enabled, Docker exposes port 8000)
// Prod (Vercel): empty string — vercel.json rewrites /api/* → Render backend
const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

async function jsonFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

export const api = {
  listMerchants: () => jsonFetch('/api/v1/merchants'),
  getDashboard: (id) => jsonFetch(`/api/v1/merchants/${id}/dashboard`),
  requestPayout: ({ merchantId, amountPaise, bankAccountId, idempotencyKey }) =>
    jsonFetch('/api/v1/payouts', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({
        merchant_id: merchantId,
        amount_paise: amountPaise,
        bank_account_id: bankAccountId,
      }),
    }),
};
