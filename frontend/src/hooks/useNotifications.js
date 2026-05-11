import { useState, useEffect, useCallback, useRef } from "react";
import api from "../services/api";

const POLL_INTERVAL = 30_000;

export default function useNotifications() {
  const [data, setData] = useState({ unread: 0, notifications: [] });
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  const fetch = useCallback(async () => {
    try {
      const res = await api.get("/notifications");
      setData(res.data);
    } catch {
      // silencieux — ne pas polluer la console si non connecté
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetch().finally(() => setLoading(false));
    timerRef.current = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [fetch]);

  const markRead = useCallback(async (id) => {
    await api.patch(`/notifications/${id}/read`);
    setData((d) => ({
      ...d,
      unread: Math.max(0, d.unread - 1),
      notifications: d.notifications.map((n) =>
        n.id === id ? { ...n, is_read: true } : n
      ),
    }));
  }, []);

  const markAllRead = useCallback(async () => {
    await api.patch("/notifications/read-all");
    setData((d) => ({
      ...d,
      unread: 0,
      notifications: d.notifications.map((n) => ({ ...n, is_read: true })),
    }));
  }, []);

  const remove = useCallback(async (id) => {
    await api.delete(`/notifications/${id}`);
    setData((d) => ({
      ...d,
      unread: d.notifications.find((n) => n.id === id && !n.is_read)
        ? Math.max(0, d.unread - 1)
        : d.unread,
      notifications: d.notifications.filter((n) => n.id !== id),
    }));
  }, []);

  return { ...data, loading, refetch: fetch, markRead, markAllRead, remove };
}
