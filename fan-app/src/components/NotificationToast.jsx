import { useEffect } from "react";

export default function NotificationToast({ notification, onClose }) {
  useEffect(() => {
    if (!notification) {
      return undefined;
    }

    const timer = setTimeout(onClose, 6000);
    return () => clearTimeout(timer);
  }, [notification, onClose]);

  if (!notification) {
    return null;
  }

  return (
    <div
      className={`notification-toast ${notification.variant || ""}`}
      role="status"
      aria-live="assertive"
      aria-atomic="true"
    >
      <button
        className="toast-close"
        onClick={onClose}
        aria-label="Dismiss notification"
      >
        <i className="bi bi-x-lg" aria-hidden="true" />
      </button>
      <div className="toast-title">{notification.title}</div>
      <div className="toast-body">{notification.body}</div>
    </div>
  );
}
