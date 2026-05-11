import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import useNotifications from "../hooks/useNotifications";
import "./NotificationBell.css";

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  return `il y a ${Math.floor(diff / 86400)} j`;
}

const TYPE_ICON = {
  status_change: "📋",
  new_cv: "📄",
};

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const { unread, notifications, markRead, markAllRead, remove } = useNotifications();

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const handleClick = async (notif) => {
    if (!notif.is_read) await markRead(notif.id);
    if (notif.link) navigate(notif.link);
    setOpen(false);
  };

  return (
    <div className="nb-root" ref={ref}>
      <button className="nb-btn" onClick={() => setOpen((o) => !o)} aria-label="Notifications">
        <span className="nb-icon">🔔</span>
        {unread > 0 && (
          <span className="nb-badge">{unread > 99 ? "99+" : unread}</span>
        )}
      </button>

      {open && (
        <div className="nb-panel">
          <div className="nb-header">
            <span className="nb-title">Notifications</span>
            {unread > 0 && (
              <button className="nb-read-all" onClick={markAllRead}>
                Tout marquer lu
              </button>
            )}
          </div>

          <div className="nb-list">
            {notifications.length === 0 ? (
              <div className="nb-empty">Aucune notification</div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`nb-item ${n.is_read ? "nb-item--read" : "nb-item--unread"}`}
                  onClick={() => handleClick(n)}
                >
                  <span className="nb-item-icon">{TYPE_ICON[n.type] || "🔔"}</span>
                  <div className="nb-item-body">
                    <div className="nb-item-title">{n.title}</div>
                    <div className="nb-item-msg">{n.message}</div>
                    <div className="nb-item-time">{timeAgo(n.created_at)}</div>
                  </div>
                  <button
                    className="nb-item-del"
                    onClick={(e) => { e.stopPropagation(); remove(n.id); }}
                    aria-label="Supprimer"
                  >×</button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
