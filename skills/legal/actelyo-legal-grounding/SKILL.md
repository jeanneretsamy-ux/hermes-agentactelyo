---
name: actelyo-legal-grounding
description: Verify French legal claims against cited primary sources.
version: 1.0.0
author: jeanneretsamy-ux, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [actelyo, legal, france, citations, verification]
    category: legal
    related_skills: [legal-data-hunter, openlegi-official-sources, actelyo-supervised-learning]
---

# Actelyo Legal Grounding Skill

This skill prepares legally grounded French-law analyses for Actelyo. It verifies factual legal claims from retrieved sources; it does not replace a lawyer's professional judgment or fabricate a citation when the source is missing.

## When to Use

Use it for a legal answer, clause review, procedural analysis, or compliance note that contains a material legal proposition, an article reference, a case reference, or a current-law assertion.

## Prerequisites

- The user has authorised the external research query when a source is not already provided.
- For official French sources, load `openlegi-official-sources` with `skill_view`.
- For broader legal research, load `legal-data-hunter` with `skill_view`.
- Use only the read-only tools discovered through the configured connector. Do not place client names, dossier identifiers, documents, or credentials in an external query.

## How to Run

1. State the jurisdiction, legal question, and effective date required.
2. Retrieve the primary or authoritative source with the loaded research skill.
3. Build the answer from the retrieved text and label any interpretation as analysis.
4. Keep a source ledger in the work product before presenting a conclusion.

## Quick Reference

- Current rule: record the source, official reference, effective or consolidation date, URL, retrieval time, and exact supporting excerpt.
- Case law: record the court, decision date, decision number when available, and source URL.
- Missing evidence: say that the point could not be verified; do not complete it from model memory.
- Conflict: show the competing sources and explain why no final conclusion is safe yet.

## Procedure

1. Separate provided facts from assumptions. Ask for the missing fact that changes the legal outcome.
2. Discover the connector tools before every external call; do not infer tool names or parameter schemas.
3. Prefer the official text in force. For a historical question, verify the applicable date instead of using the current consolidated text.
4. Link every material legal proposition to a source ledger entry. Distinguish source fact, inference, and practical recommendation.
5. Check article numbers, court references, dates, and quotations against the retrieved text before delivery.
6. If a source does not support the proposition, remove or qualify the proposition.
7. Retain a compact evidence list in the draft so a lawyer can reproduce the review.

## Pitfalls

- A search snippet, an LLM answer, or an uncited secondary article is not proof of a legal rule.
- Do not state that a source is exhaustive when the connector reports incomplete coverage.
- Do not convert a source from a different jurisdiction into French law.
- Do not claim personalised legal advice without a lawyer's review of the complete file.

## Verification

Before delivery, confirm that every material legal assertion has a source ledger entry and that each reference exists in the retrieved text. When verification fails, the output says exactly which assertion remains unverified.
