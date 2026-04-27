import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';

export function useDashboard(merchantId, intervalMs = 3000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!merchantId) return;
    try {
      const r = await api.getDashboard(merchantId);
      if (r.ok) setData(r.data);
      else setError(r.data?.error || `HTTP ${r.status}`);
    } catch (err) {
      setError(`Network error: ${err.message}`);
    }
  }, [merchantId]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, intervalMs);
    return () => clearInterval(t);
  }, [refresh, intervalMs]);

  return { data, error, refresh };
}
