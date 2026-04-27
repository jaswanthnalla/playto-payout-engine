// In dev (Docker), the backend is exposed on host port 8000.
// CORS_ALLOW_ALL_ORIGINS = True so direct calls work fine.
// In production, set VITE_API_BASE to the Railway backend URL.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

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
