import { Routes, Route, Link } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import LandingPage from "./pages/LandingPage";
import DashboardPage from "./pages/DashboardPage";
import AnalyzeSpeechPage from "./pages/AnalyzeSpeechPage";
import AnalysisResultsPage from "./pages/AnalysisResultsPage";
import ReferenceLibraryPage from "./pages/ReferenceLibraryPage";
import DatasetManagerPage from "./pages/DatasetManagerPage";
import AnalysisHistoryPage from "./pages/AnalysisHistoryPage";
import SettingsPage from "./pages/SettingsPage";
import { Empty } from "./components/ui";
import { archiveMode } from "./config/hosting";
import HostedAnalysisPage from "./pages/HostedAnalysisPage";
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/analyze" element={archiveMode ? <HostedAnalysisPage /> : <AnalyzeSpeechPage />} />
        <Route path="/analyses/:analysisId" element={<AnalysisResultsPage />} />
        <Route path="/references" element={<ReferenceLibraryPage />} />
        <Route path="/datasets" element={<DatasetManagerPage />} />
        <Route path="/history" element={<AnalysisHistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="*"
          element={
            <Empty
              title="This page is unavailable"
              action={<Link to="/dashboard">Return to workspace</Link>}
            />
          }
        />
      </Route>
    </Routes>
  );
}
