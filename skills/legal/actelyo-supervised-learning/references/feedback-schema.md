# Actelyo feedback record

Store one redacted JSON object per validated feedback event in an authorised local workspace.

```json
{
  "feedback_id": "fb-2026-0001",
  "occurred_at": "2026-10-08T10:00:00+02:00",
  "skill": "actelyo-legal-grounding",
  "task_kind": "legal-research",
  "observation": "Redacted description of the correction.",
  "evidence_ref": "official-source-or-reviewed-test-reference",
  "proposed_change": "Small instruction or template change.",
  "status": "pending_review"
}
```

Allowed statuses are `pending_review`, `approved`, `rejected`, and `superseded`. Do not include client names, dossier identifiers, credentials, full documents, or unredacted correspondence.
