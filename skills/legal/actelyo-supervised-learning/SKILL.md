---
name: actelyo-supervised-learning
description: Turn validated corrections into reviewable skill updates.
version: 1.0.0
author: jeanneretsamy-ux, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [actelyo, legal, feedback, evaluation, skills, review]
    category: legal
    related_skills: [actelyo-legal-grounding, actelyo-legal-work-product]
---

# Actelyo Supervised Learning Skill

This skill turns validated human feedback into small, reviewable improvements to Hermes skills. It does not train model weights, publish a change, or learn from unverified client material without review.

## When to Use

Use it after a lawyer or authorised reviewer corrects a result, rejects an unsupported claim, approves a better workflow, or reports the same operational failure twice.

## Prerequisites

- Keep the feedback in the authorised local workspace with an evidence reference or redacted example.
- Obtain a human validation for every proposed skill change.
- Load the affected skill with `skill_view` before proposing a patch through `skill_manage`.
- Do not use a client document as training data. Store only the minimum redacted feedback necessary to explain the correction.

## How to Run

1. Record the feedback as a structured, redacted item using `references/feedback-schema.md`.
2. Identify whether the issue is a factual source gap, a workflow error, a missing guardrail, or a template defect.
3. Propose the smallest skill or template change that prevents recurrence.
4. Stage the change through `skill_manage`; a human reviews the diff and approves or rejects it.

## Quick Reference

- Immediate proposal: one safety or source-grounding failure.
- Pattern proposal: two substantially identical validated corrections.
- Skill changes: `skill_manage` then human diff and approval.
- Model changes: never automatic; require a separate evaluated release process.

## Procedure

1. Create a feedback item with its identifier, date, redacted observation, affected skill, evidence reference, proposed change, and status `pending_review`.
2. Compare the correction to existing skill instructions. Do not duplicate a rule already present; explain why it was not followed instead.
3. Test the proposed instruction on a redacted example and record expected versus observed behaviour.
4. Use `skill_manage` only after reading the full target skill. Keep the patch narrow and preserve existing safety requirements.
5. Review the staged diff with the human owner. Approve only when the evaluation evidence and regression check are recorded.
6. If rejected, retain the feedback item as rejected and do not silently retry the same change.
7. Use `/refine` after a correction to request an immediate background review; the configured review may also make a staged proposal after ordinary work.

## Pitfalls

- Feedback is not proof until a human validates it against the source or workflow requirement.
- Never let an automatic review approve its own patch.
- Never turn a single user preference into a universal legal rule.
- Do not upload feedback, client documents, or legal sources to an external provider without the user's separate authorisation.

## Verification

A completed improvement has a redacted feedback record, a linked evidence reference, a staged skill diff, a human approval, and a regression example. If any element is missing, the item stays `pending_review`.
