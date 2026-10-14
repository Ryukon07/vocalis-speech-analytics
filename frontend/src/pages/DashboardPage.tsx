import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Plus,
  ArrowUpRight,
  AudioLines,
  CheckCircle2,
  Gauge,
  Library,
  Database,
} from "lucide-react";
import { api } from "../api/client";
import { Card, PageTitle, Empty, Loading, ErrorNotice } from "../components/ui";
import HistoryTable from "../components/analysis/HistoryTable";
export default function DashboardPage() {
  const query = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const d = query.data;
  return (
    <>
      <PageTitle
        eyebrow="YOUR SPEECH WORKSPACE"
        title="Workspace overview"
        description="A clearer picture of your recordings, references and delivery."
        action={
          <Link className="btn btn-primary" to="/analyze">
            <Plus size={17} /> New analysis
          </Link>
        }
      />
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : (
        d && (
          <>
            <div className="stats-grid">
              {[
                {
                  icon: AudioLines,
                  label: "Total analyses",
                  value: d.total,
                  note: "All saved jobs, including demos",
                },
                {
                  icon: CheckCircle2,
                  label: "Completed",
                  value: d.completed,
                  note: `${d.real_completed} completed with real models`,
                },
                {
                  icon: Gauge,
                  label: "Average delivery score",
                  value:
                    d.average_score == null ? "—" : d.average_score.toFixed(1),
                  note:
                    d.average_score == null
                      ? "Available after real model results"
                      : "Real results only · out of 100",
                },
                {
                  icon: Library,
                  label: "Reference library",
                  value: d.references,
                  note: `${d.groups} contrastive dataset groups`,
                },
              ].map((s) => (
                <Card className="stat" key={s.label}>
                  <div className="row between">
                    <span className="muted">{s.label}</span>
                    <s.icon size={19} />
                  </div>
                  <strong>{s.value}</strong>
                  <p className="muted tiny">{s.note}</p>
                </Card>
              ))}
            </div>
            <Card>
              <div className="section-title">
                <div>
                  <h2>Recent analyses</h2>
                  <p className="muted">
                    Your latest recordings and processing activity.
                  </p>
                </div>
                <Link to="/history" className="text-link">
                  View all <ArrowUpRight size={16} />
                </Link>
              </div>
              <HistoryTable items={d.recent} />
            </Card>
            <div className="grid-two">
              <Card>
                <div className="section-title">
                  <h2>Delivery patterns</h2>
                  <Gauge size={19} />
                </div>
                {d.frequent_flaws.length ? (
                  d.frequent_flaws.map((f) => (
                    <div className="list-row" key={f.type}>
                      <span>{f.type.replaceAll("_", " ")}</span>
                      <span className="badge">{f.count} intervals</span>
                    </div>
                  ))
                ) : (
                  <Empty
                    title="Patterns need real results"
                    description="Frequently detected flaws appear here when a real analysis provider is connected."
                  />
                )}
              </Card>
              <Card>
                <div className="section-title">
                  <h2>Build your reference foundation</h2>
                  <Database size={19} />
                </div>
                <p className="muted">
                  Organize strong deliveries, paired variants and timestamped
                  labels in one workspace.
                </p>
                <div className="library-links">
                  <Link to="/references">
                    <Library size={20} />
                    <span>
                      Reference library
                      <small>{d.references} recordings available</small>
                    </span>
                    <ArrowUpRight size={16} />
                  </Link>
                  <Link to="/datasets">
                    <Database size={20} />
                    <span>
                      Contrastive dataset
                      <small>{d.groups} groups with shared transcripts</small>
                    </span>
                    <ArrowUpRight size={16} />
                  </Link>
                </div>
              </Card>
            </div>
          </>
        )
      )}
    </>
  );
}
