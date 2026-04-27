const STATUS_COLORS = {
  PENDING: 'bg-yellow-100 text-yellow-800',
  PROCESSING: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
};

export default function PayoutHistory({ payouts }) {
  return (
    <div className="bg-white rounded-xl shadow p-5 border border-gray-100">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Payout History</h2>
      {!payouts?.length ? (
        <p className="text-sm text-gray-400">No payouts yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b">
                <th className="pb-2">ID</th>
                <th className="pb-2">Amount</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Attempts</th>
                <th className="pb-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {payouts.map((p) => (
                <tr key={p.id}>
                  <td className="py-2 font-mono text-xs text-gray-400">
                    {p.id.slice(0, 8)}…
                  </td>
                  <td className="py-2 font-medium">
                    ₹{(p.amount_paise / 100).toFixed(2)}
                  </td>
                  <td className="py-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_COLORS[p.status]
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="py-2 text-xs text-gray-500">{p.attempts}</td>
                  <td className="py-2 text-xs text-gray-400">
                    {new Date(p.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
