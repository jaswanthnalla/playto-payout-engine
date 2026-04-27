import { useState } from 'react';
import { api } from '../api';

export default function PayoutForm({ merchantId, bankAccounts, onSuccess }) {
  const [amount, setAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState(bankAccounts?.[0]?.id || '');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    const idempotencyKey = crypto.randomUUID();
    const amountPaise = Math.round(parseFloat(amount) * 100);

    if (!Number.isFinite(amountPaise) || amountPaise <= 0) {
      setMessage({ type: 'error', text: 'Enter a valid amount' });
      setLoading(false);
      return;
    }

    const r = await api.requestPayout({
      merchantId,
      amountPaise,
      bankAccountId,
      idempotencyKey,
    });

    if (r.ok) {
      setMessage({ type: 'success', text: `Payout queued: ₹${amount}` });
      setAmount('');
      onSuccess?.();
    } else {
      setMessage({ type: 'error', text: r.data?.error || 'Request failed' });
    }
    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl shadow p-5 border border-gray-100">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Request Payout</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs text-gray-500">Amount (INR)</label>
          <input
            type="number"
            step="0.01"
            min="1"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm mt-1"
            placeholder="e.g. 500.00"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">Bank Account</label>
          <select
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm mt-1"
          >
            {bankAccounts?.map((acc) => (
              <option key={acc.id} value={acc.id}>
                {acc.bank} — {acc.account}
              </option>
            ))}
          </select>
        </div>
        {message && (
          <p
            className={`text-xs ${
              message.type === 'error' ? 'text-red-500' : 'text-green-600'
            }`}
          >
            {message.text}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? 'Submitting…' : 'Request Payout'}
        </button>
      </form>
    </div>
  );
}
