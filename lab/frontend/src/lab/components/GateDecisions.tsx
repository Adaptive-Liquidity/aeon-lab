import React, { useEffect, useRef, useState } from "react";
import type { LabApiClient } from "../api/client";

interface Props {
  client: LabApiClient;
}

interface GateEvent {
  project_id: string;
  track: string;
  stage: string;
  event: string;
  payload: any;
  timestamp: number;
}

export default function GateDecisions({ client }: Props): JSX.Element {
  const [events, setEvents] = useState<GateEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const url = client.base.replace(/^http/, "ws") + "/ws/events";
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = ev => {
      try {
        const e: GateEvent = JSON.parse(ev.data);
        if (e?.event && ["gate_passed", "gate_blocked", "rollback"].includes(e.event)) {
          setEvents(prev => [e, ...prev].slice(0, 100));
        }
      } catch {
        // ignore
      }
    };
    return () => ws.close();
  }, [client]);

  return (
    <table className="gate-decisions">
      <thead>
        <tr>
          <th>time</th>
          <th>track/stage</th>
          <th>event</th>
          <th>confidence</th>
          <th>findings</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e, i) => {
          const ts = new Date(e.timestamp * 1000).toLocaleTimeString();
          const conf = e.payload?.confidence?.toFixed?.(2) ?? "—";
          const findings = (e.payload?.findings || []).slice(0, 1).join("; ");
          return (
            <tr key={i} className={e.event}>
              <td>{ts}</td>
              <td>{e.track}/{e.stage}</td>
              <td>{e.event}</td>
              <td>{conf}</td>
              <td>{findings}</td>
            </tr>
          );
        })}
        {events.length === 0 && <tr><td colSpan={5} className="empty">No gate events yet.</td></tr>}
      </tbody>
    </table>
  );
}
