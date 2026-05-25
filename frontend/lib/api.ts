export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

export type BankListItem = {
  bank_folder_name: string;
  status?: string | null;
  source_format?: string | null;
  updated_at?: string | null;
};

export async function listBanks(): Promise<{ banks: BankListItem[] }> {
  return apiFetch("/api/banks");
}

export async function createBank(form: FormData): Promise<{ bank_folder_name: string; vector_chunks: number; evidence_claims: number; messages: string[] }> {
  return apiFetch("/api/banks", { method: "POST", body: form });
}

export async function listBankItems(bankName: string): Promise<{ items: any[] }> {
  return apiFetch(`/api/banks/${encodeURIComponent(bankName)}/items`);
}

export async function listBankFiles(bankName: string): Promise<{ files: any[] }> {
  return apiFetch(`/api/banks/${encodeURIComponent(bankName)}/files`);
}

export async function readBankFile(bankName: string, path: string): Promise<{ path: string; title: string; content: string }> {
  const qs = new URLSearchParams({ path });
  return apiFetch(`/api/banks/${encodeURIComponent(bankName)}/files/content?${qs.toString()}`);
}

export async function tailorResume(body: { bank_name: string; jd_text: string }): Promise<{ bank_folder_name: string; resume_id: string; messages: string[] }> {
  return apiFetch("/api/tailor", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
}

export async function listDocs(): Promise<{ docs: { slug: string; title: string }[] }> {
  return apiFetch("/api/docs");
}

export async function getDoc(slug: string): Promise<{ slug: string; title: string; content: string }> {
  return apiFetch(`/api/docs/${encodeURIComponent(slug)}`);
}

export async function getResumeLatex(resumeId: string): Promise<{ resume_id: string; latex: string; updated_at: string }> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/latex`);
}

export async function putResumeLatex(resumeId: string, latex: string): Promise<{ resume_id: string; status: string; updated_at: string }> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/latex`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ latex })
  });
}

export async function compileResume(resumeId: string, latex?: string): Promise<any> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/compile`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ latex: latex ?? null })
  });
}

export async function getResumeMarkdown(resumeId: string): Promise<{ resume_id: string; markdown: string }> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/markdown`);
}

export async function getResumeText(resumeId: string): Promise<{ resume_id: string; text: string }> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/text`);
}

export async function getResumeTraceability(resumeId: string): Promise<{ resume_id: string; traceability: any }> {
  return apiFetch(`/api/resumes/${encodeURIComponent(resumeId)}/traceability`);
}
