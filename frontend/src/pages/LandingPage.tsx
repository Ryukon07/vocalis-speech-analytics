import { Link } from "react-router-dom";
import {
  AudioLines,
  ArrowRight,
  Waves,
  Timer,
  BarChart3,
  ScanLine,
  ArrowUpRight,
} from "lucide-react";
import { brand } from "../config/brand";
import { archiveMode } from "../config/hosting";
export default function LandingPage() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <Link to="/" className="brand">
          <span className="brand-icon">
            <AudioLines />
          </span>
          {brand.name}
        </Link>
        <div className="row">
          {archiveMode ? <Link to="/history">Real reports</Link> : <a href="#workflow">How it works</a>}
          <Link to="/dashboard">
            Workspace <ArrowUpRight size={15} />
          </Link>
        </div>
      </nav>
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">
              <span className="dot" /> SPEECH INTELLIGENCE & DELIVERY ANALYTICS
            </p>
            <h1>
              Your voice.
              <br />
              Understood in detail.
            </h1>
            <p className="hero-description">
              Move from vague feedback to a clear view of your delivery. Compare
              a speech with a reference, explore every interval, and connect
              feedback to its evidence.
            </p>
            <div className="row wrap">
              <Link className="btn btn-primary" to={archiveMode ? "/history" : "/analyze"}>
                {archiveMode ? "Browse Real Reports" : "Analyze a Speech"} <ArrowRight size={18} />
              </Link>
              <Link className="btn btn-secondary" to="/dashboard">
                Explore Dashboard
              </Link>
              {archiveMode && <a className="btn btn-secondary" href={`${import.meta.env.BASE_URL}downloads/vocalis-final-demo.mp4`} target="_blank" rel="noreferrer">Watch demo video</a>}
            </div>
            <p className="muted tiny hero-note">
              {archiveMode ? "Laptop-independent report viewer · Real saved results · New analysis requires the full workspace" : "Local speech models · Measured acoustic feedback · Saved reports"}
            </p>
          </div>
          <div className="hero-visual">
            <div className="row between">
              <span className="eyebrow">DELIVERY, IN CONTEXT</span>
              <span className="badge demo">ILLUSTRATIVE VIEW</span>
            </div>
            <div className="visual-wave" aria-hidden="true">
              {Array.from({ length: 62 }, (_, i) => (
                <i
                  key={i}
                  style={{
                    height: `${15 + Math.abs(Math.sin(i * 1.7)) * 60 + Math.abs(Math.sin(i * 0.17)) * 30}px`,
                    opacity: i > 24 && i < 39 ? 0.95 : 0.45,
                  }}
                />
              ))}
            </div>
            <div className="visual-range">
              <span>00:00</span>
              <span>00:15</span>
              <span>00:30</span>
            </div>
            <div className="visual-callout">
              <Timer size={20} />
              <div>
                <strong>See where delivery changes</strong>
                <p>
                  Timestamped intervals. Visible evidence. Clear next steps.
                </p>
              </div>
            </div>
            <div className="row between visual-caption">
              <span>
                <i className="dot violet" /> Participant
              </span>
              <span>
                <i className="dot teal" /> Reference
              </span>
              <span>Illustrative graphic</span>
            </div>
          </div>
        </section>
        <section className="feature-grid">
          {[
            {
              icon: Waves,
              title: "Acoustic detail",
              text: "Inspect pitch, energy, pacing, pauses and word recognition with measured evidence.",
            },
            {
              icon: ScanLine,
              title: "Precise moments",
              text: "Find flaw intervals and jump directly to the corresponding audio.",
            },
            {
              icon: BarChart3,
              title: "Your evaluation rubric",
              text: "Configure dimensions and weights for repeatable delivery scoring.",
            },
            {
              icon: Timer,
              title: "Explainable feedback",
              text: "Keep measurements, predictions and interpretation visibly distinct.",
            },
          ].map((f) => (
            <div className="feature-card" key={f.title}>
              <f.icon size={22} />
              <h3>{f.title}</h3>
              <p className="muted">{f.text}</p>
            </div>
          ))}
        </section>
        <section className="workflow" id="workflow">
          <p className="eyebrow">FROM RECORDING TO UNDERSTANDING</p>
          <h2>A clear path through your speech.</h2>
          <div className="grid-three">
            {[
              "Bring your recording and transcript",
              "Choose a reference and rubric",
              "Explore evidence and export feedback",
            ].map((s, i) => (
              <div key={s}>
                <span className="step-number">0{i + 1}</span>
                <h3>{s}</h3>
              </div>
            ))}
          </div>
          <p className="notice">
            Speech analysis runs locally with pretrained models and your selected
            reference. Scores are relative heuristics, with the measurements
            available for review. Optional demo reports are clearly labelled.
          </p>
          <Link className="btn btn-primary" to="/analyze">
            Open the workspace <ArrowRight size={18} />
          </Link>
        </section>
      </main>
      <footer className="landing-footer">
        {brand.name} · {brand.tagline}
        <span>Built for Track C · Multimodal AI Hackathon 2026</span>
      </footer>
    </div>
  );
}
