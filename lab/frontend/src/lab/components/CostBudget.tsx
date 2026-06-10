import React, { useEffect, useState } from "react";
import type { LabApiClient } from "../api/client";

interface Props {
  client: LabApiClient;
}

export default function CostBudget({ client }: Props): JSX.Element {
  const [data, setData] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [project, setProject] = useState<string>("");

  const refresh = async () => {
    try {
      const r = await client.cost(project || undefined);
      setData(r);
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  };

  useEffect(() => {
    refresh();
    const h = setInterval(refresh, 10000);
    return () => clearInterval(h);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  return (
    <div className="cost-budget">
      <div className="form-row inline">
        <input
          placeholder="Filter project_id (optional)"
          value={project}
          onChange={e => setProject(e.target.value)}
        />
        <button onClick={refresh}>Refresh</button>
      </div>
      {err && <div className="lab-error">{err}</div>}
      {data && (
        <>
          <div className="cost-total">
            Total spend: <strong>${data.total_usd?.toFixed(4) ?? "0.0000"}</strong>
          </div>
          <div className="cost-grid">
            <CostBucket title="By model" bucket={data.by_model || {}} />
            <CostBucket title="By stage" bucket={data.by_stage || {}} />
            <CostBucket title="By project" bucket={data.by_project || {}} />
          </div>
        </>
      )}
    </div>
  );
}

function CostBucket({ title, bucket }: { title: string; bucket: Record<string, number> }) {
  const rows = Object.entries(bucket).sort((a, b) => b[1] - a[1]).slice(0, 10);
  return (
    <div className="cost-bucket">
      <h3>{title}</h3>
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>${v.toFixed(4)}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td className="empty">no data</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
