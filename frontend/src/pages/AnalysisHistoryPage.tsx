import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, RotateCcw, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { useAction } from "../hooks/useAction";
import {
  PageTitle,
  Card,
  Loading,
  ErrorNotice,
  Button,
  Confirm,
  Pagination,
} from "../components/ui";
import HistoryTable from "../components/analysis/HistoryTable";
export default function AnalysisHistoryPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [deleting, setDeleting] = useState<string>();
  const q = useQuery({
    queryKey: ["analyses", search, status, offset],
    queryFn: () =>
      api.analyses(
        `?search=${encodeURIComponent(search)}&status=${status}&offset=${offset}`,
      ),
    refetchInterval: 3000,
  });
  const del = useAction(
    (id: string) => api.deleteAnalysis(id),
    "Analysis deleted.",
    () => setDeleting(undefined),
  );
  const retry = useAction(
    (id: string) => api.retry(id),
    "Analysis queued for retry.",
  );
  return (
    <>
      <PageTitle
        eyebrow="YOUR RECORD"
        title="Analysis history"
        description="Revisit reports and recover jobs across page refreshes."
        action={
          <Link className="btn btn-primary" to="/analyze">
            <Plus size={17} /> New analysis
          </Link>
        }
      />
      <Card>
        <div className="toolbar">
          <label className="search-field">
            <Search size={17} />
            <input
              aria-label="Search analyses"
              placeholder="Search recording or analysis ID"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </label>
          <select
            aria-label="Filter status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {["queued", "processing", "completed", "failed", "cancelled"].map(
              (s) => (
                <option key={s}>{s}</option>
              ),
            )}
          </select>
        </div>
        <ErrorNotice error={q.error} />
        {q.isPending ? (
          <Loading />
        ) : (
          <HistoryTable
            items={q.data?.items || []}
            actions={(a) => (
              <div className="row">
                <Link className="text-link" to={`/analyses/${a.id}`}>
                  Open
                </Link>
                {a.status === "failed" && (
                  <Button
                    variant="ghost"
                    aria-label="Retry analysis"
                    disabled={retry.isPending}
                    onClick={() => retry.mutate(a.id)}
                  >
                    <RotateCcw size={16} />
                  </Button>
                )}
                {!["queued", "processing"].includes(a.status) && (
                  <Button
                    variant="ghost"
                    aria-label="Delete analysis"
                    onClick={() => setDeleting(a.id)}
                  >
                    <Trash2 size={16} />
                  </Button>
                )}
              </div>
            )}
          />
        )}
        {q.data && (
          <Pagination
            offset={offset}
            total={q.data.total}
            onChange={setOffset}
          />
        )}
      </Card>
      <Confirm
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(undefined)}
        busy={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </>
  );
}
