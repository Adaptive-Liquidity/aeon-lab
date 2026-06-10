# Lab frontend extension

This folder layers ECC lab dashboard panels on top of Claw-AI-Lab's existing React frontend.

## Wiring

After running `node lab/scripts/vendor-claw.js --physical`, the Claw frontend lives at `lab/frontend/` (this directory) with a `package.json` and Vite config. Add the lab routes:

```tsx
// src/main.tsx or your top-level layout
import "./lab/styles.css";
import { LabApp } from "./lab";

export default function App() {
  return (
    <Routes>
      <Route path="/lab/*" element={<LabApp />} />
      {/* existing Claw routes... */}
    </Routes>
  );
}
```

Set `window.__ECC_LAB_API__` (or `ECC_LAB_API_URL` env var) to the lab API gateway (default `http://localhost:8810`).

## Panels

- `WorkItemQueue` — submit a brief; router classifies it as research/engineering.
- `EngineeringTrack` — phase strip + active engineering workflows.
- `EventStream` — live tail of `events.jsonl` via WebSocket.
- `GateDecisions` — quality-stack verdicts (allow / blocked / rollback).
- `CostBudget` — cost ledger rollup with filterable project_id.
- `ProvenanceInspector` — content-hash chain entries for a project.
- `MCPPolicyAudit` — per-role MCP broker allow-lists.
