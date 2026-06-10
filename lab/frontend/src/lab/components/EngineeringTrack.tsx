import React, { useEffect, useState } from "react";
import type { LabApiClient } from "../api/client";

const ENGINEERING_PHASES = [
  "intake",
  "research_reuse",
  "plan",
  "scaffold",
  "implement",
  "review",
  "commit",
] as const;

type Phase = (typeof ENGINEERING_PHASES)[number];

interface Props {
  client: LabApiClient;
}

export default function EngineeringTrack({ client }: Props): JSX.Element {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tick = async () => {
      try {
        const list = await client.listWorkflows();
        setWorkflows((list.workflows || []).filter(w => w.type === "EngineeringWorkflow"));
        setError(null);
      } catch (e) {
        setError(String(e));
      }
    };
    tick();
    const h = setInterval(tick, 5000);
    return () => clearInterval(h);
  }, [client]);

  if (error) return <div className="lab-error">{error}</div>;
  return (
    <div className="engineering-track">
      <div className="phase-strip">
        {ENGINEERING_PHASES.map(p => (
          <span key={p} className="phase-pill">{p}</span>
        ))}
      </div>
      <ul className="workflow-list">
        {workflows.length === 0 ? (
          <li className="empty">No engineering workflows running.</li>
        ) : (
          workflows.map(w => (
            <li key={w.workflow_id} className="workflow-row">
              <code>{w.workflow_id}</code>
              <span className="status">{w.status}</span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
