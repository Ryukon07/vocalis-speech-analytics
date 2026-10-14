import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, X, AlertCircle, Inbox, Loader2 } from "lucide-react";

export function Button({
  children,
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p className="muted">{description}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 className="spin" /> Loading workspace…
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}
export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div className="notice error" role="alert">
      <AlertCircle size={18} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  ) : null;
}
export function DemoBadge() {
  return <span className="badge demo">DEMO / MOCK ANALYSIS</span>;
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content">
          <div className="row between">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" aria-label="Close dialog">
                <X size={18} />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            {description || "Manage this workspace record."}
          </Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Confirm({
  open,
  onOpenChange,
  onConfirm,
  busy,
  title = "Delete this record?",
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: () => void;
  busy?: boolean;
  title?: string;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description="This removes the selected record. Linked records may need to be removed first."
    >
      <div className="row end">
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Keep record
        </Button>
        <Button variant="danger" disabled={busy} onClick={onConfirm}>
          {busy ? "Deleting…" : "Delete record"}
        </Button>
      </div>
    </Modal>
  );
}
type Toast = { id: number; text: string; error: boolean };
const ToastContext = createContext<(text: string, error?: boolean) => void>(
  () => {},
);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const notify = (text: string, error = false) => {
    const id = Date.now() + Math.random();
    setItems((v) => [...v, { id, text, error }]);
    setTimeout(() => setItems((v) => v.filter((t) => t.id !== id)), 6000);
  };
  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div className={`toast ${t.error ? "error" : ""}`} key={t.id}>
            {t.error ? <AlertCircle size={18} /> : <Check size={18} />}
            <span>{t.text}</span>
            <button
              onClick={() => setItems((v) => v.filter((i) => i.id !== t.id))}
              aria-label="Dismiss notification"
            >
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
export function Pagination({
  offset,
  total,
  onChange,
  limit = 20,
}: {
  offset: number;
  total: number;
  onChange: (v: number) => void;
  limit?: number;
}) {
  return (
    <div className="pagination">
      <span className="muted">
        {total
          ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`
          : "0 records"}
      </span>
      <div className="row">
        <Button
          variant="secondary"
          disabled={!offset}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
