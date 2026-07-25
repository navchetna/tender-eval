import type { ReactNode } from "react";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(32,32,28,.4)] px-4"
      onClick={onCancel}
    >
      <div
        className="expand w-full max-w-[400px] rounded-[13px] border-[0.5px] border-line bg-surface p-5 shadow-[0_20px_60px_-15px_rgba(30,28,24,.4)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-[15px] font-semibold text-ink">{title}</div>
        <div className="mt-[8px] text-[13px] leading-[1.5] text-ink-soft">{message}</div>
        <div className="mt-[18px] flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn rounded-[9px] border-[0.5px] border-line-strong bg-surface px-4 py-2 text-[13px] text-ink disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`btn rounded-[9px] border-none px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60 ${
              danger ? "bg-bad-dot" : "bg-accent"
            }`}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
