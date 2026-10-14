import { Link } from "react-router-dom";
import { Card, PageTitle } from "../components/ui";
import { liveWorkspace } from "../config/hosting";

export default function HostedAnalysisPage() {
  return <>
    <PageTitle eyebrow="HOSTED REPORT VIEWER" title="Explore real speech analyses" description="This free hosted dashboard stays available while the project laptop is offline." />
    <Card>
      <h2>Saved results, complete evidence</h2>
      <p>Browse real model-generated scores, aligned transcripts, acoustic charts and timestamped feedback. Audio replay, spoken feedback and JSON, CSV and PDF downloads work here.</p>
      <p>New uploads, microphone analysis and editing need the Python inference server. They are unavailable in this report viewer. The separate full workspace works while its serving laptop is online.</p>
      <div className="row wrap">
        <Link className="btn btn-primary" to="/history">Browse saved reports</Link>
        <a className="btn btn-secondary" href={liveWorkspace} target="_blank" rel="noreferrer">Open full live workspace</a>
        <a className="btn btn-secondary" href="https://github.com/Ryukon07/vocalis-speech-analytics">Code and local setup</a>
      </div>
    </Card>
  </>;
}
