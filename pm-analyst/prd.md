# PM Analyst — Product Overview

## What Is PM Analyst?

PM Analyst is a web application that converts meeting recordings, transcripts, and notes into structured project management artifacts. Users pick and add meeting content (call tanscripts) and other relvant files from their onedrive and the application produces summaries, epics, features, and user stories that follow organizational templates. Once approved, it would add them to the Azure DevOps Services.
The agent would converse with the user (the PM) to collect missing information that is not in the transcript or cannot be derived from provided context. It also highlights potential conflicts and areas of concenrn.

## Problem Statement

Project managers spend significant time manually translating meeting discussions into actionable work items. This process is repetitive, time-consuming, and prone to inconsistency. PM Analyst automates this conversion, reducing effort and improving consistency.

## User Workflow

1. **Upload** — User can pick among their previous call transcripts, their files in onedrive  or uploads one or more meeting files (TXT, DOCX, PDF, or Markdown).
2. **Summarize** — The application generates a structured meeting summary with key discussion points, decisions, and action items.
3. **Review & Edit** — Agent would ask the user to provide missing information one at a time in a convesational way. ensures that all the required information is gathered.
4. **Select Work Item Types** — agent suggests but the User chooses which artifacts to generate: Epics, Features, and/or User Stories.
5. **Generate** — The application produces work items following organizational templates and add them to Azure DevOps Services through their APIs.

## Supported File Formats

| Format | Extension | Extraction Method |
|--------|-----------|-------------------|
| Plain Text | .txt | Direct read |
| Markdown | .md | Direct read |
| Word Document | .docx | Client-side extraction (Mammoth.js) |
| PDF | .pdf | Client-side extraction (PDF.js) |
| API | ... | Directly read from team meet transcripts and onedrive |


All outputs follow configurable organizational templates and are returned as structured data inside Azure DevOps Services.

## Architecture Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | NextJS, shadcn | User interface, file upload, converstional layer, view of the current asset, final approval |
| Backend | Python (FastAPI) | API layer, session management, authentication, template serving |
| AI Agent | Google ADK on Vertex AI Agent Engine | Content analysis and generation using Gemini model |
| Deployment | Docker on Google Cloud Run |  |

## Key Characteristics

- **Session-based** — Each user session maintains conversation context so the agent can reference prior outputs (e.g., linking stories to features).
- **Template-driven** — All generated content follows configurable organizational templates.
- **Editable outputs** — Users can edit any generated content before finalizing.
- **Multi-file support** — Multiple meeting files can be uploaded and processed together.
- **Access control** — Email-based authentication with an allow-list.
