import { useEffect, useState } from 'react';
import { api } from './api';
import { useDashboard } from './hooks/usePayouts';
import BalanceCard from './components/BalanceCard';
import PayoutForm from './components/PayoutForm';
import PayoutHistory from './components/PayoutHistory';
import TransactionList from './components/TransactionList';

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [selected, setSelected] = useState('');
  const [loadError, setLoadError] = useState(null);
  const { data: dashboard, refresh } = useDashboard(selected);

  useEffect(() => {
    api.listMerchants().then((r) => {
      if (r.ok && r.data.length) {
        setMerchants(r.data);
        setSelected(r.data[0].id);
      } else {
        setLoadError(r.data?.error || `Failed to load merchants (HTTP ${r.status})`);
      }
    }).catch((err) => {
      setLoadError(`Network error: ${err.message}`);
    });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Playto Payout Engine</h1>
            <p className="text-xs text-gray-500 mt-1">Cross-border payouts for Indian merchants</p>
          </div>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm bg-white"
          >
            {merchants.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        {loadError ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm font-medium text-red-700">Could not reach backend</p>
            <p className="text-xs text-red-500 mt-1">{loadError}</p>
            <p className="text-xs text-gray-500 mt-2">Make sure the backend is running on <code>http://localhost:8000</code></p>
          </div>
        ) : !dashboard ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-1 space-y-4">
              <BalanceCard
                available={dashboard.available_balance_paise}
                held={dashboard.held_balance_paise}
              />
              <PayoutForm
                merchantId={selected}
                bankAccounts={dashboard.bank_accounts}
                onSuccess={refresh}
              />
            </div>
            <div className="md:col-span-2 space-y-4">
              <PayoutHistory payouts={dashboard.recent_payouts} />
              <TransactionList entries={dashboard.recent_entries} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
