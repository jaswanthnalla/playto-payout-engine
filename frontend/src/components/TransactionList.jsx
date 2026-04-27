export default function TransactionList({ entries }) {
  return (
    <div className="bg-white rounded-xl shadow p-5 border border-gray-100">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Ledger Entries</h2>
      {!entries?.length ? (
        <p className="text-sm text-gray-400">No entries yet.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {entries.map((e) => (
            <li key={e.id} className="py-2 flex justify-between text-sm">
              <div>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded mr-2 ${
                    e.entry_type === 'CREDIT'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-red-50 text-red-700'
                  }`}
                >
                  {e.entry_type}
                </span>
                <span className="text-gray-600">{e.description}</span>
              </div>
              <div className="text-right">
                <p
                  className={`font-medium ${
                    e.entry_type === 'CREDIT' ? 'text-green-700' : 'text-red-700'
                  }`}
                >
                  {e.entry_type === 'CREDIT' ? '+' : '-'}₹{(e.amount / 100).toFixed(2)}
                </p>
                <p className="text-xs text-gray-400">
                  {new Date(e.created_at).toLocaleTimeString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
