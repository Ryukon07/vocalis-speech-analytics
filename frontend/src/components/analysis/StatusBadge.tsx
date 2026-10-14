import type { Status } from "../../types";
export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`badge status-${status}`}>
      <i />
      {status[0].toUpperCase() + status.slice(1)}
    </span>
  );
}
