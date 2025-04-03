import React from "react"
import { createRoot } from "react-dom/client"
import Detection from "./Detection"

const rootElement = document.getElementById("root")
if (!rootElement) throw new Error("Failed to find the root element")

const root = createRoot(rootElement)
root.render(
  <React.StrictMode>
    <Detection />
  </React.StrictMode>
)