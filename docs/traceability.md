# Traceability

## What this does
Explains how generated bullets map back to evidence and how to use traceability during review.

## Why it exists
Without traceability, generation is hard to trust. Traceability gives you an audit trail from each bullet to the underlying evidence in your Experience Bank.

## Step-by-step usage
1. Generate a tailored resume.
2. Open the **Resume Workspace**.
3. Open the **Traceability** tab.
4. For any bullet you edit, keep the meaning aligned with its evidence (or remove it).

## What happens internally
- Each generated bullet is only emitted if it can be linked to one or more evidence claims.
- The workspace stores a traceability structure: generated text → evidence IDs → source section/source text.

## Common mistakes
- Treating unlinked bullets as “fine” (if it doesn’t map to evidence, it’s unverified).
- Editing bullets to a different claim than the evidence supports.

## Recommended next steps
- Use traceability to audit your final bullets, then export the PDF.

