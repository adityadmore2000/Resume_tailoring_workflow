"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { listBanks, tailorResume } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export default function TailorPage() {
  const router = useRouter();
  const sp = useSearchParams();
  const preselected = sp.get("bank");

  const banksQuery = useQuery({ queryKey: ["banks"], queryFn: listBanks });
  const bankOptions = (banksQuery.data?.banks ?? []).map((b) => ({ value: b.bank_folder_name, label: b.bank_folder_name }));

  const [bank, setBank] = React.useState<string | null>(preselected);
  const [jdText, setJdText] = React.useState("");
  const [lastLog, setLastLog] = React.useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => tailorResume({ bank_name: bank ?? "", jd_text: jdText }),
    onSuccess: (data) => {
      setLastLog(`Tailored resume generated successfully: ${data.resume_id}`);
      router.push(`/resumes/${encodeURIComponent(data.resume_id)}/preview`);
    }
  });

  function clearForm() {
    setBank(preselected ?? null);
    setJdText("");
    setLastLog(null);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Tailor Resume</h1>
          <p className="mt-1 text-sm text-slate-700">
            Step 3 of 4 — Select an Experience Bank and provide a Job Description. Only verified evidence is used.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={clearForm}>
            Clear Form
          </Button>
          <Link href="/banks">
            <Button variant="outline">Experience Banks</Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>How this works</CardTitle>
          <CardDescription>Retrieval → verification → assembly from your bank.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-slate-700 space-y-2">
          <div>- Unsupported skills/tools are not added automatically.</div>
          <div>- Resume uploads are not required during tailoring.</div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <div className="text-sm font-medium">Experience Bank</div>
          {bankOptions.length === 0 ? (
            <div className="space-y-2">
              <Select value={null} onChange={setBank} placeholder="No Experience Banks found" options={[]} disabled />
              <Link href="/banks/create">
                <Button>Create Experience Bank</Button>
              </Link>
            </div>
          ) : (
            <Select value={bank} onChange={setBank} placeholder="Select an Experience Bank" options={bankOptions} />
          )}
          <div className="text-xs text-slate-600">What is an Experience Bank? A reusable knowledge base extracted from your master resume.</div>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">Job Description</div>
          <Textarea value={jdText} onChange={(e) => setJdText(e.target.value)} placeholder="Paste the JD here…" />
          <div className="text-xs text-slate-600">Hint: keep the JD specific. The retriever uses it to include (and exclude) content.</div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !bank || !jdText.trim()}>
          {mutation.isPending ? "Tailoring…" : "Tailor Resume"}
        </Button>
        <div className="text-xs text-slate-600">Why was a skill excluded? It wasn’t supported by verified evidence in your bank.</div>
      </div>

      {mutation.error ? <div className="text-sm text-red-600">{String(mutation.error)}</div> : null}
      {lastLog ? <div className="text-sm text-slate-700">{lastLog}</div> : null}
    </div>
  );
}

