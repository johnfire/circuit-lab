import { useEffect, useState } from 'react';

export function useDraftScope() {
  const [session, setSession] = useState<{ ready: boolean; scope: string | null }>({ ready: false, scope: null });
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch('/api/session', { signal: controller.signal, cache: 'no-store' });
        const payload: unknown = await response.json();
        if (!response.ok || typeof payload !== 'object' || payload === null || !('draft_scope' in payload)
          || typeof payload.draft_scope !== 'string' || !/^[a-f0-9]{64}$/.test(payload.draft_scope)) throw new Error('Invalid storage scope');
        setSession({ ready: true, scope: payload.draft_scope });
      } catch { if (!controller.signal.aborted) setSession({ ready: true, scope: null }); }
    };
    void load();
    return () => controller.abort();
  }, []);
  return session;
}
