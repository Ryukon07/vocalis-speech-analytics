import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { Analysis } from "../../types";
import StatusBadge from "./StatusBadge";
import { DemoBadge, Empty } from "../ui";
import { formatDate } from "../../lib/validation";
export default function HistoryTable({
  items,
  actions,
}: {
  items: Analysis[];
  actions?: (a: Analysis) => React.ReactNode;
}) {
  if (!items.length)
    return (
      <Empty
        title="No analyses yet"
        description="Upload a recording and choose a reference to create your first analysis."
        action={
          <Link className="btn btn-primary" to="/analyze">
            Analyze a speech
          </Link>
        }
      />
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Recording</th>
            <th>Reference</th>
            <th>Status</th>
            <th>Score</th>
            <th>Flaws</th>
            <th>Created</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td>
                <Link className="record-link" to={`/analyses/${a.id}`}>
                  {a.participant_filename || a.id.slice(0, 8)}
                </Link>
                <small className="table-small">
                  {a.execution_mode === "mock" ? (
                    <DemoBadge />
                  ) : (
                    `ID ${a.id.slice(0, 8)}`
                  )}
                </small>
              </td>
              <td>{a.reference_title || "—"}</td>
              <td>
                <StatusBadge status={a.status} />
              </td>
              <td>
                {a.overall_score == null
                  ? "—"
                  : `${a.overall_score.toFixed(1)} / 100`}
              </td>
              <td>{a.status === "completed" ? a.flaw_count : "—"}</td>
              <td className="muted">{formatDate(a.created_at)}</td>
              <td>
                {actions ? (
                  actions(a)
                ) : (
                  <Link to={`/analyses/${a.id}`} aria-label="Open analysis">
                    <ArrowUpRight size={17} />
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
