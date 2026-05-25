# Tailoring

## What this does
Explains how to generate a role-specific resume using a Job Description + an Experience Bank.

## Why it exists
Tailoring is not “rewrite everything.” It is *retrieval + verification + assembly* from a trusted source-of-truth (your Experience Bank).

## Step-by-step usage
1. Go to **Tailor Resume**.
2. Select an **Experience Bank**.
3. Paste a Job Description (or upload `.txt` / `.md`).
4. Click **Tailor**.
5. You’ll be taken to the **Resume Workspace** to review/export.

## What happens internally
1. The JD is parsed into structured requirements.
2. Retrieval selects the most relevant evidence from your bank (vector + metadata signals).
3. Evidence is verified deterministically against the bank’s claims.
4. Only verified evidence is assembled into:
   - tailored bullets
   - tailored markdown/text
   - LaTeX resume output

## Common mistakes
- Expecting new skills/tools to be added without evidence.
- Providing a vague JD (retrieval works best with specific role requirements).
- Clearing the form expecting it to delete artifacts (Clear Form resets inputs only).

## Recommended next steps
- Open the Resume Workspace and review traceability before exporting.

