import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppRouter } from "./app/router";
import { createQueryClient } from "./app/queryClient";
import "./styles.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("index.html is missing #root");
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={createQueryClient()}>
      <AppRouter />
    </QueryClientProvider>
  </StrictMode>,
);
