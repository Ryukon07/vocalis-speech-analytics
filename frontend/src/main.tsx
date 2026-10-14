import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { archiveMode } from "./config/hosting";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "./components/ui";
import App from "./App";
import { brand } from "./config/brand";
import "./styles.css";
document.title = `${brand.name} · ${brand.tagline}`;
document.documentElement.dataset.density =
  localStorage.getItem("vocalis-display") || "comfortable";
const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 10000 } },
});
const Router = archiveMode ? HashRouter : BrowserRouter;
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <Router>
        <ToastProvider>
          <App />
        </ToastProvider>
      </Router>
    </QueryClientProvider>
  </React.StrictMode>,
);
