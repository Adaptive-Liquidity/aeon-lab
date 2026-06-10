import React, { useState } from "react";
import type { LabApiClient } from "../api/client";

interface Props {
  client: LabApiClient;
}

export default function ProvenanceInspector({ client }: Props): JSX.Element {
  const [projectId, setProjectId] = useState("");
  const [entries, setEntries] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!projectId.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await client.provenance(projectId.trim());
      setEntries(r.entries || []);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="provenance-inspector">
      <div className="form-row inline">
        <input
          placeholder="project_id"
          value={projectId}
          onChange={e => setProjectId(e.target.value)}
        />
        <button onClick={load} disabled={loading || !projectId.trim()}>
          {loading ? "Loading…" : "Load"}
        </button>
      </div>
      {err && <div className="lab-error">{err}</div>}
      <table className="ledger-table">
        <thead>
          <tr>
            <th>seq</th>
            <th>track</th>
            <th>stage</th>
            <th>role</th>
            <th>kind</th>
            <th>artifact</th>
            <th>chain</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={e.id}>
              <td>{i + 1}</td>
              <td>{e.track}</td>
              <td>{e.stage}</td>
              <td>{e.agent_role}</td>
              <td>{e.kind}</td>
              <td><code>{(e.artifact_sha256 || "").slice(0, 12)}</code></td>
              <td><code>{(e.previous_hash || "").slice(0, 12)}</code></td>
            </tr>
          ))}
          {entries.length === 0 && <tr><td colSpan={7} className="empty">No ledger entries.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
