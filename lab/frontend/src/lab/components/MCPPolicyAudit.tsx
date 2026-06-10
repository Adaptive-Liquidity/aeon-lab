import React, { useEffect, useState } from "react";
import type { LabApiClient } from "../api/client";

interface Props {
  client: LabApiClient;
}

export default function MCPPolicyAudit({ client }: Props): JSX.Element {
  const [roles, setRoles] = useState<Record<string, any> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    client
      .policy()
      .then(r => setRoles(r.roles))
      .catch(e => setErr(String(e)));
  }, [client]);

  if (err) return <div className="lab-error">{err}</div>;
  if (!roles) return <div>Loading…</div>;

  return (
    <table className="mcp-policy-audit">
      <thead>
        <tr>
          <th>role</th>
          <th>servers</th>
          <th>egress</th>
          <th>fs write</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(roles).map(([role, body]: [string, any]) => (
          <tr key={role}>
            <td><code>{role}</code></td>
            <td>{(body.servers || []).join(", ")}</td>
            <td>
              {body.can_egress ? (
                <code title={(body.egress_allowlist || []).join("\n")}>
                  {(body.egress_allowlist || []).length} hosts
                </code>
              ) : (
                <span className="deny">denied</span>
              )}
            </td>
            <td>{body.can_write_filesystem ? "yes" : "no"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
