import { AlertCircle, Activity } from "lucide-react";
import { ReactNode, useEffect, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busyLabel?: string;
  busy?: boolean;
  confirmDisabled?: boolean;
  children?: ReactNode;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busyLabel = "Aguarde...",
  busy = false,
  confirmDisabled = false,
  children,
  onCancel,
  onConfirm,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;
  const titleId = `confirm-title-${title.replace(/\W+/g, "-").toLowerCase()}`;
  const descriptionId = `${titleId}-description`;

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    const focusTimer = window.setTimeout(() => cancelRef.current?.focus(), 0);

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onCancelRef.current();
    }

    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      window.clearTimeout(focusTimer);
      previousFocus.current?.focus();
    };
  }, [busy, open]);

  if (!open) return null;

  return (
    <div
      className="confirm-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <section
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <AlertCircle size={28} aria-hidden="true" />
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        {children}
        <div className="dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="dialog-cancel"
            onClick={onCancel}
            disabled={busy}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="dialog-confirm"
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
          >
            {busy && <Activity size={16} aria-hidden="true" />}
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
