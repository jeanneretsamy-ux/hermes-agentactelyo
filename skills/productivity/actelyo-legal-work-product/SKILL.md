---
name: actelyo-legal-work-product
description: Prepare legal documents, invoices, and email drafts safely.
version: 1.0.0
author: jeanneretsamy-ux, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [actelyo, legal, document, invoice, email, draft]
    category: productivity
    related_skills: [actelyo-legal-grounding, actelyo-supervised-learning]
---

# Actelyo Legal Work Product Skill

This skill prepares reviewable drafts for documents, invoices, and messages in Actelyo. It creates a draft and an action checklist; it does not send mail, create a binding invoice, sign a document, or write to PolyOffice without a configured official connector and an explicit action-time approval.

## When to Use

Use it when a user asks for a legal document, invoice, client message, attachment list, or task based on a provided or retrieved dossier.

## Prerequisites

- Confirm the exact dossier or workspace and the intended recipient before using client data.
- Use `read_file` to inspect the approved template, source document, or provided data.
- Use `actelyo-legal-grounding` with `skill_view` when the draft contains legal assertions.
- Treat an external write as unavailable until a configured official connector exposes the operation and the user explicitly approves the concrete payload.

## How to Run

1. Collect the approved template, dossier facts, recipient, language, and completion deadline.
2. Produce a labelled draft with unresolved fields and an attachment manifest.
3. Validate factual data, totals, and legal references before requesting any external action.
4. Present the exact action payload for approval when a connector is available.

## Quick Reference

- Document: title, parties, version date, source facts, placeholders, legal source ledger, reviewer.
- Invoice: issuer, client, matter, line items, currency, tax basis, payment terms, invoice identifier, missing fields.
- Email: recipient, subject, body, attachments, purpose, and send status set to `draft`.
- External write: explicit approval, idempotency key, connector result, and read-back verification.

## Procedure

1. Read the source files and state the information that is missing or ambiguous.
2. Select only an approved template. Keep template wording intact unless the user asks for a change.
3. Use `write_file` to create a draft in the authorised workspace. Mark all assumptions and placeholders clearly.
4. For an invoice, calculate only from supplied amounts and flag an absent tax rate, legal entity, or payment term. Never invent mandatory accounting data.
5. For an email, create a draft and attachment manifest. Do not call a send-capable tool by default.
6. If an official PolyOffice or mail connector becomes available, request explicit approval of the exact recipient, amount, attachments, and final text at the action moment.
7. After an authorised write, read back the resulting record and report its identifier and status.

## Pitfalls

- Do not treat a local draft as sent, signed, invoiced, or filed.
- Do not use a generic client name when the dossier identity is ambiguous.
- Do not expose client data in external research prompts.
- Do not fabricate invoice numbers, payment terms, attachments, or signature status.

## Verification

The draft passes when its source facts, placeholders, legal assertions, and attachments can be reviewed. An external action passes only after the official connector reports success and a read-back confirms the resulting object.
