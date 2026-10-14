---
title: "Actelyo Rag Backend — Search, question and cite locally indexed documents"
sidebar_label: "Actelyo Rag Backend"
description: "Search, question and cite locally indexed documents"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Actelyo Rag Backend

Search, question and cite locally indexed documents.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/legal/actelyo-rag-backend` |
| Version | `1.0.0` |
| Author | JEANNERETSAMY (@jeanneretsamy-ux) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `actelyo`, `legal`, `rag`, `documents`, `mcp` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Actelyo RAG Backend

Use this skill when the user asks Actelyo Law Harness to work against their own indexed documents or a document workspace.
Trigger for searching, questioning, summarizing, comparing or citing indexed documents, workspaces, uploaded files or a local knowledge base.

Use the local MCP server `actelyo-rag` rather than reindexing or copying documents into Actelyo Law Harness. Prefer these tools:

- `actelyo_rag_list_workspaces` to discover available workspaces.
- `actelyo_rag_vector_search` when the user needs source chunks, evidence, citations, or a retrieval-only check.
- `actelyo_rag_query` with `mode: "query"` when the user asks a question that should be answered only from retrieved documents.
- `actelyo_rag_query` with `mode: "chat"` only when the user asks for a more conversational answer using the workspace context.

Default workspace: `mon-espace-de-travail`.

If Actelyo RAG is not running, tell the user to launch Actelyo RAG and retry. Do not upload private files to external services for this workflow.
