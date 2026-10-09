---
title: "Legal Data Hunter — Research legal sources through authenticated MCP access"
sidebar_label: "Legal Data Hunter"
description: "Research legal sources through authenticated MCP access"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Legal Data Hunter

Research legal sources through authenticated MCP access.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/legal/legal-data-hunter` |
| Version | `1.0.0` |
| Author | Actelyo |
| License | MIT |
| Platforms | windows |
| Tags | `actelyo`, `legal`, `research`, `mcp`, `legal-data-hunter` |
| Related skills | [`grounded-citations`](../../bundled/research/research-grounded-citations.md), [`openlegi-official-sources`](../../bundled/legal/legal-openlegi-official-sources.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Legal Data Hunter

Use this skill for legal research that requires the Legal Data Hunter source catalogue. It operates only through the local Polybot connector on the same Windows user session. The provider token remains in the Windows DPAPI SecretVault and must never be copied into prompts, skill files, logs, or request arguments.

## Preconditions

- Polybot is available at the configured local application root.
- `LEGAL_DATA_HUNTER_TOKEN` is present in that application's SecretVault.
- The user has approved the external legal research query. Send only an abstract legal question: no client identity, dossier identifier, parties, contact details, or secret.

## Procedure

1. Ask the connector to discover `tools/list` before selecting a capability.
2. Use only these read-only operations when exposed: `search`, `resolve_reference`, `get_document`, `discover_countries`, `discover_sources`, and `get_filters`.
3. Treat `report_source_issue` and any write-capable remote tool as unavailable.
4. Save the provider, jurisdiction, source identifiers, reference date, and exact excerpts needed to support the answer.
5. Verify each material legal proposition against the retrieved primary text or an authoritative official source. Do not turn a search result into an uncited legal conclusion.

## Guardrails

- Never send client facts, names, documents, credentials, or dossier data to the provider.
- Do not infer a tool name or its parameter schema: discovery is mandatory before every call.
- Report unavailable jurisdictions, missing source text, and conflicting material instead of filling gaps from model memory.
- External research is read-only; no source correction, publication, or account change is allowed.

## Verification

A successful check reports that the connector is configured and lists the current remote tools. A successful research result records the discovered tool name, jurisdiction, source reference, retrieval time, and citations; it never includes the provider token.
