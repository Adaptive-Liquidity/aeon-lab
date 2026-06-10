import React, { useEffect, useRef, useState } from "react";

interface Props {
  wsUrl: string;
  max?: number;
}

interface LabEvent {
  project_id: string;
  track: string;
  stage: string;
  event: string;
  timestamp: number;
  payload?: any;
}

export default function EventStream({ wsUrl, max = 200 }: Props): JSX.Element {
  const [events, setEvents] = useState<LabEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = ev => {
      try {
        const e: LabEvent = JSON.parse(ev.data);
        setEvents(prev => [e, ...prev].slice(0, max));
      } catch {
        // ignore malformed lines
      }
    };
    return () => ws.close();
  }, [wsUrl, max]);

  return (
    <div className="event-stream">
      <div className="stream-header">
        <span className={connected ? "dot ok" : "dot down"} />
        {connected ? "Live" : "Disconnected"} — {events.length} events
      </div>
      <ul className="stream-list">
        {events.map((e, i) => (
          <li key={i} className={`stream-event ${e.event}`}>
            <code>{new Date(e.timestamp * 1000).toLocaleTimeString()}</code>
            <span className="proj">{e.project_id}</span>
            <span className="pair">{e.track}/{e.stage}</span>
            <span className="evt">{e.event}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
