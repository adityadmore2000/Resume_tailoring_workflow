# FAQ

### Why do banks exist?
To avoid re-uploading and re-parsing a resume for every job, and to keep a stable stored resume tree that tailoring can reference.

### Why is resume upload not needed during tailoring?
Tailoring uses your selected bank stored in Postgres (`resumes` + `resume_nodes`) plus the scoped Qdrant resume_nodes index.

### What is traceability?
An audit trail that records which resume_nodes were retrieved/matched and which spans were rewritten.

