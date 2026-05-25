# Experience Banks

## What this does
Explains what an Experience Bank is, what it contains, and how it powers resume tailoring without repeated uploads.

## Why it exists
Recruiters care about evidence-backed claims. An Experience Bank turns a master resume into a reusable source-of-truth that can be retrieved and audited.

## Step-by-step usage
1. Go to **Experience Banks → Create Experience Bank**.
2. Use a stable bank name (e.g., `aditya_ai_master_resume`).
3. Upload your master resume (MVP: `.tex` / `.txt`; PDF is planned).
4. Generate the bank.
5. Go to **Preview Experience Bank** to review the extracted content.

## What happens internally
- The system treats a bank as a resume knowledge base with three layers:
  - **KBRecord**: the reusable/editable professional unit (e.g. work experience, project, summary, education, capability, reusable bullet).
  - **EvidenceClaim**: an atomic factual support extracted from the source resume.
  - **QdrantPoint**: a semantic-search index entry for a KBRecord/EvidenceClaim.

## Editing model (AI-safe)
- Users edit **KBRecords** via the **AI Bank Editor** (natural-language instructions).
- The AI proposes a change, the system validates it against **EvidenceClaims**, and only then the user can approve it.
- **Source-of-truth factual fields are immutable by default** (company, role title, dates, location, education, explicit metrics).
- Qdrant is a retrieval index only; it is not the trusted editable truth store.

## Common mistakes
- Using unstable bank names (you’ll reuse the name during tailoring).
- Overwriting banks accidentally (only overwrite if you intend to replace the source-of-truth).
- Treating the bank as a raw filesystem (use Preview for human-readable review).

## Recommended next steps
- Preview the bank to confirm evidence looks correct → Tailor a resume using that bank.
