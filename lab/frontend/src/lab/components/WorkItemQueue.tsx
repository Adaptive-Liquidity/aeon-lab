import React, { useState } from "react";
import type { LabApiClient } from "../api/client";

interface Props {
  client: LabApiClient;
}

export default function WorkItemQueue({ client }: Props): JSX.Element {
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [track, setTrack] = useState<"" | "research" | "engineering">("");
  const [budget, setBudget] = useState<number>(50);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await client.submit({
        title: title.trim(),
        description: desc.trim() || title.trim(),
        track: track || undefined,
        budget_usd: budget,
      });
      setLast(r);
      setTitle("");
      setDesc("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="work-item-queue">
      <div className="form-row">
        <input
          placeholder="Task title"
          value={title}
          onChange={e => setTitle(e.target.value)}
        />
      </div>
      <div className="form-row">
        <textarea
          placeholder="Description (optional)"
          value={desc}
          onChange={e => setDesc(e.target.value)}
          rows={3}
        />
      </div>
      <div className="form-row inline">
        <select value={track} onChange={e => setTrack(e.target.value as any)}>
          <option value="">Auto-route</option>
          <option value="research">Research</option>
          <option value="engineering">Engineering</option>
        </select>
        <input
          type="number"
          min={1}
          step={1}
          value={budget}
          onChange={e => setBudget(Number(e.target.value))}
          style={{ width: 100 }}
          aria-label="Budget USD"
        />
        <button onClick={submit} disabled={busy || !title.trim()}>
          {busy ? "Submitting…" : "Submit"}
        </button>
      </div>
      {err && <div className="lab-error">{err}</div>}
      {last && (
        <div className="last-submission">
          <strong>{last.project_id}</strong> → {last.track} (confidence {last.confidence.toFixed(2)})
          <div className="rationale">{last.rationale}</div>
        </div>
      )}
    </div>
  );
}
