const inr = (paise) =>
  ((paise || 0) / 100).toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export default function BalanceCard({ available, held }) {
  const settled = (available || 0) - (held || 0);
  return (
    <div className="bg-white rounded-xl shadow p-5 border border-gray-100">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Merchant Balance</h2>
      <div className="space-y-3">
        <div>
          <p className="text-xs text-gray-400">Available (ledger net)</p>
          <p className="text-2xl font-bold text-green-600">{inr(available)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Held (PENDING + PROCESSING)</p>
          <p className="text-lg font-semibold text-amber-500">{inr(held)}</p>
        </div>
        <div className="pt-2 border-t">
          <p className="text-xs text-gray-400">Spendable now</p>
          <p className="text-base font-medium text-gray-700">{inr(settled)}</p>
        </div>
      </div>
    </div>
  );
}
