---
name: actelyo-rag-backend
description: Use Actelyo RAG as the local document-retrieval backend for Actelyo Law Harness. Trigger when the user asks to search, question, summarize, compare, or cite their own indexed documents, workspaces, uploaded files, or local knowledge base.
user-invocable: true
---

# Actelyo RAG Backend

Use this skill when the user asks Actelyo Law Harness to work against their own indexed documents or a document workspace.

Use the local MCP server `actelyo-rag` rather than reindexing or copying documents into Actelyo Law Harness. Prefer these tools:

- `actelyo_rag_list_workspaces` to discover available workspaces.
- `actelyo_rag_vector_search` when the user needs source chunks, evidence, citations, or a retrieval-only check.
- `actelyo_rag_query` with `mode: "query"` when the user asks a question that should be answered only from retrieved documents.
- `actelyo_rag_query` with `mode: "chat"` only when the user asks for a more conversational answer using the workspace context.

Default workspace: `mon-espace-de-travail`.

If Actelyo RAG is not running, tell the user to launch Actelyo RAG and retry. Do not upload private files to external services for this workflow.

