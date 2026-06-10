/**
 * ECC Lab — extended dashboard root.
 *
 * Mounts the engineering track, work-item queue, provenance inspector,
 * cost budget, gate decisions, and MCP policy audit panels alongside
 * Claw's existing research pipeline UI.
 */

import React, { useEffect, useState } from "react";
import EngineeringTrack from "./components/EngineeringTrack";
import WorkItemQueue from "./components/WorkItemQueue";
import ProvenanceInspector from "./components/ProvenanceInspector";
import CostBudget from "./components/CostBudget";
import GateDecisions from "./components/GateDecisions";
import MCPPolicyAudit from "./components/MCPPolicyAudit";
import EventStream from "./components/EventStream";
import { LabApiClient } from "./api/client";

const API_BASE =
  (typeof window !== "undefined" && (window as any).__ECC_LAB_API__) ||
  process.env.ECC_LAB_API_URL ||
  "http://localhost:8810";

export default function LabApp(): JSX.Element {
  const [client] = useState(() => new LabApiClient(API_BASE));
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    client.health().then(() => setHealthy(true)).catch(() => setHealthy(false));
  }, [client]);

  return (
    <div className="lab-root">
      <header className="lab-header">
        <h1>ECC + Claw Lab</h1>
        <span className={`lab-status ${healthy === false ? "down" : healthy ? "ok" : "unknown"}`}>
          {healthy === false ? "API offline" : healthy ? "online" : "checking…"}
        </span>
      </header>

      <div className="lab-grid">
        <section className="lab-panel">
          <h2>Work item queue</h2>
          <WorkItemQueue client={client} />
        </section>

        <section className="lab-panel">
          <h2>Engineering track</h2>
          <EngineeringTrack client={client} />
        </section>

        <section className="lab-panel">
          <h2>Live events</h2>
          <EventStream wsUrl={`${API_BASE.replace(/^http/, "ws")}/ws/events`} />
        </section>

        <section className="lab-panel">
          <h2>Gate decisions</h2>
          <GateDecisions client={client} />
        </section>

        <section className="lab-panel">
          <h2>Cost & budgets</h2>
          <CostBudget client={client} />
        </section>

        <section className="lab-panel">
          <h2>Provenance</h2>
          <ProvenanceInspector client={client} />
        </section>

        <section className="lab-panel">
          <h2>MCP broker policy</h2>
          <MCPPolicyAudit client={client} />
        </section>
      </div>
    </div>
  );
}
