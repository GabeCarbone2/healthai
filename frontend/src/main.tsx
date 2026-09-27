import React from "react";
import ReactDOM from "react-dom/client";

import "@fontsource/open-sans/latin-400.css";
import "@fontsource/open-sans/latin-500.css";
import "@fontsource/open-sans/latin-600.css";
import "@fontsource/open-sans/latin-700.css";

import App from "./App";
import "./styles.css";
import "./refresh.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
