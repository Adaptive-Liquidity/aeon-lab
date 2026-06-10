/** Minimal client for the lab FastAPI gateway. */

export class LabApiClient {
  constructor(public base: string) {}

  private async _json<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.base}${path}`, {
      headers: { "content-type": "application/json", ...(init?.headers || {}) },
      ...init,
    });
    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText} for ${path}`);
    }
    return (await res.json()) as T;
  }

  health() {
    return this._json<{ ok: boolean; version: string }>("/api/lab/health");
  }

  submit(payload: {
    title: string;
    description: string;
    track?: "research" | "engineering";
    budget_usd?: number;
  }) {
    return this._json<{
      project_id: string;
      workflow_id: string;
      track: string;
      confidence: number;
      rationale: string;
    }>("/api/lab/submit", { method: "POST", body: JSON.stringify(payload) });
  }

  listWorkflows() {
    return this._json<{ workflows: any[]; error?: string }>("/api/lab/workflows");
  }

  describeWorkflow(id: string) {
    return this._json<any>(`/api/lab/workflows/${encodeURIComponent(id)}`);
  }

  cancelWorkflow(id: string) {
    return this._json<{ cancelled: boolean }>(
      `/api/lab/workflows/${encodeURIComponent(id)}/cancel`,
      { method: "POST" }
    );
  }

  cost(project?: string) {
    const q = project ? `?project_id=${encodeURIComponent(project)}` : "";
    return this._json<any>(`/api/lab/cost${q}`);
  }

  provenance(project: string) {
    return this._json<any>(`/api/lab/provenance/${encodeURIComponent(project)}`);
  }

  policy() {
    return this._json<{ roles: Record<string, any> }>("/api/lab/policy");
  }
}
