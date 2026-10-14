import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
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
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
