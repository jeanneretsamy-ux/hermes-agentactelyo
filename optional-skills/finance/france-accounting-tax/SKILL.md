---
name: france-accounting-tax
description: Prepare traceable French accounting and tax drafts.
version: 1.0.0
author: Jeanneretsamy (jeanneretsamy-ux), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [France, comptabilité, FEC, fiscalité, formulaires]
    related_skills: [excel-author, pdf]
---

# French Accounting and Tax Skill

Use this workflow to prepare traceable bookkeeping work, bank reconciliations (rapprochement bancaire), FEC checks, and drafts for French tax forms. It does not replace a chartered accountant or tax professional, and it never submits declarations or payments. Work only from documents the user is authorized to provide; do not infer missing amounts or silently apply a tax regime.

## When to Use

Use for French-law accounting and tax preparation: bank reconciliation, accounting review, FEC validation, IFU 2561 (including 2561 bis/ter), 2777-SD, 2042, 2044/2044-SPE, or 2759-SD. Confirm which legal person, taxpayer, fiscal year, jurisdiction, and role the user means before processing.

## Prerequisites

- `web_search` or `browser_navigate` to retrieve the current official form, notice, and instructions from impots.gouv.fr, BOFiP, Legifrance, or the applicable public authority.
- `read_file`, `search_files`, `terminal`, and `patch` for local evidence and validation; use `pdf` or `xlsx` skills when handling those formats.
- Source documents: bookkeeping export and chart of accounts; statements in CSV/OFX/QIF or equivalent; invoices/receipts; prior-period balances and filings; and taxpayer/entity details relevant to the requested return.

## How to Run

1. Identify the taxpayer/client, legal entity, jurisdiction, accounting basis, fiscal year/period, declarant role, requested output, and whether this is a draft, correction, or first filing. For a second country, ask for its exact name before applying its rules.
2. Retrieve the current official form and its notice for the requested tax year. Record the URL, publication/millésime, retrieval date, and relevant paragraphs or boxes. Re-check each time; never reuse a prior-year box map without validation.
3. Build a source inventory and an input-to-output mapping. Keep source values, derived values, assumptions, and unresolved questions distinct. Cite a source document/page/row for every populated amount.
4. Reconcile calculations to source totals and prior-period carryforwards. Flag discrepancies and missing evidence; never fill a box by guesswork.
5. Prepare a clearly labelled draft worksheet or form. Have the user or their accountant review every unresolved/conditional item. Do not file, transmit, pay, sign, or amend a return without a separate explicit instruction and the authorized filing mechanism.

## Quick Reference

| Work | Required result |
|---|---|
| Bank reconciliation | Statement-to-ledger matching, balance bridge, unmatched/duplicate/ambiguous exceptions |
| FEC | Validate the taxpayer's accounting export against the current LPF A.47 A-1 requirements; never manufacture a FEC from bank rows |
| 2561 / IFU | Determine whether declarant is an établissement payeur/obligated filer; choose 2561, 2561 bis and/or 2561 ter from current notice |
| 2777-SD | Determine withholding/prepayment obligation and period; current form requires online declaration and corresponding online payment |
| 2042 | Household income-tax return draft; confirm household, residency, income categories, prefilled data and tax year |
| 2044 | Unfurnished rental income under the appropriate real-property regime; assess 2044-SPE/other annexes and micro-foncier eligibility first |
| 2759-SD | Only for relevant transfers of social rights not recorded in an instrument; distinguish registration from company-registry formalities |

## Procedure

### Accounting close and bank reconciliation

1. Preserve originals read-only. Record file names, account/IBAN suffix, currency, statement period, opening/closing balances, and row counts. Do not expose full account identifiers in summaries.
2. Normalize dates, signed amounts, currencies, references, and descriptions into a working copy. Preserve original values and locale interpretation (decimal comma, separators, date order).
3. Match exact amount/currency and compatible dates/references first. For fees, grouped settlements, transfers, refunds, and split payments, create a proposed match only with supporting evidence. Similarity is a review signal, never proof.
4. Present each bank row as matched, unmatched, duplicate, or ambiguous and link matched entries to ledger journal/entry and source document. Do not create journal entries automatically from bank lines.
5. Recompute: opening bank balance + statement movements = closing bank balance; opening ledger balance + posted movements = closing ledger balance. Explain timing items and every residual. Mark reconciled only if the residual is zero or the reviewer explicitly accepts documented timing differences.
6. Produce an exception list and an audit trail of inputs, matching rules, overrides, reviewer, and timestamp.

### FEC export and validation

1. Obtain the accounting system's export for the exact entity and fiscal year, including opening balances and post-inventory entries where required. A bank statement or reconstructed spreadsheet is not a statutory FEC.
2. Consult the current consolidated LPF A.47 A-1 text and official FEC specification. Validate separator/encoding, header, field order and count for the taxpayer's accounting regime, date formats, sequence, journal/account fields, debit/credit numeric fields, opening balances, and chronologically validated entries.
3. Check each entry is balanced; debit/credit are nonnegative and not both populated; required fields are present; dates fall in the period or are explained opening/closing entries; and journal/entry numbering is consistent. Report the precise row and rule for each error.
4. Never “repair” accounting semantics, reorder validated entries, delete lines, invent missing accounts, or emit a compliant-looking file from incomplete records. Return a validation report and request a corrected source export. Preserve a hash of the input and output where available.

### Tax form workflows

For every form, first identify who is legally responsible for the filing. These form numbers refer to different taxpayer roles and are not interchangeable.

- **2561 / IFU:** The IFU summarizes securities transactions and capital income reported by obligated payers. Confirm payer status, calendar year, beneficiaries, residency, transaction types and applicable 2561/2561 bis/2561 ter pages. Reconcile beneficiary totals to payment ledgers and withholding declarations. Do not prepare an individual 2042 by copying payer-side IFU values without recipient-specific tax instructions.
- **2777-SD:** This is a payer-side declaration for certain capital-income withholdings and levies, not a general taxpayer income return. Confirm payment month, type of income, beneficiary status/residency, applicable rates and exemptions using current official guidance. Cross-check the return against gross payment ledger, deductions/withholding accounts, and payment amount. Current official 2026 form states online filing and online payment; never initiate either.
- **2042:** Confirm the tax household, dependants, residence, tax year, income sources and prefilled declaration. Populate only boxes supported by evidence and the current official notice. Reconcile wages, pensions, investment income, property income, credits and withholding to third-party statements and annexes. Flag foreign income, non-resident/departure cases, unusual deductions, or missing prefilled data for review rather than assuming treatment.
- **2044:** Determine whether the property is unfurnished, the taxpayer's ownership/SCI share, the applicable regime and whether 2044-SPE or a different annex is required. Collect property-by-property rent, recoverable charges, copropriété provisions and year-end adjustment, insurance, management, taxes, repairs, loan interest, prior deficits and supporting invoices. Apply current-year rules and box mappings from the official notice; tie net result and carryforwards to 2042. Do not treat furnished rental receipts as 2044 income.
- **2759-SD:** Confirm transfer date, rights/security type, company form, number transferred/total, price and charges, market value where relevant, real-estate-heavy-company status, acquisition origin/date/price, parties and residence, deed status and exemptions. Use 2759 only if the official scope applies; if the transfer is recorded by an instrument, if eligibility is uncertain, or a special regime is claimed, stop and verify the required route with the current notice/professional. Distinguish tax registration from RCS/company filings; 2759 alone does not complete corporate registry formalities. Check the filing/payment deadline from current guidance.

### Deliverables and review

Deliver (a) the draft, (b) a source-to-field mapping, (c) assumptions and unresolved items, (d) reconciliation/check results, and (e) the official form/notice references and retrieval dates. Clearly label each amount as source, calculated, carried forward, or pending. Request professional review for interpretation-dependent issues; the final reviewer must confirm identity, year, legal regime, all amounts, and filing readiness.

## Pitfalls

- Do not treat the law firm's own management accounts as a client's 2042/2044 or payer-side 2561/2777 obligations.
- Do not assume a “France + another country” selection defines the second jurisdiction. Ask which country; tax treaties and residency can change the result.
- Do not use 2044 for furnished rentals or select 2044-SPE based only on a property address.
- Do not treat an IFU as a self-filed individual income declaration; the filer role matters.
- Do not claim that a FEC is compliant based only on 18 familiar field names: applicable regime, sequence, content and current standard all matter.
- Do not file, sign, pay, or send client personal/tax data to a third party based on a draft request.

## Verification

- Independently recompute totals from source rows and require explicit equality checks for every reconciliation.
- Confirm every form box against the current official form and notice for the requested year; record links and version dates.
- Confirm no unresolved material exceptions are hidden and no unsupported values were inserted.
- Label output “DRAFT — NOT FILED” until a qualified reviewer approves it and the user explicitly authorizes filing.

## Official references

- Form 2561 and 2561 bis/ter: https://www.impots.gouv.fr/formulaire/2561/declaration-recapitulative-des-operations-sur-valeurs-mobilieres-et-revenus-de-capi
- Form 2777-SD: https://www.impots.gouv.fr/formulaire/2777-sd/revenus-de-capitaux-mobiliers-prelevement-et-retenue-la-source
- Form 2042: https://www.impots.gouv.fr/formulaire/2042/declaration-des-revenus
- Form 2044 and 2044-SPE: https://www.impots.gouv.fr/formulaire/2044/declaration-des-revenus-fonciers
- Form 2759-SD: https://www.impots.gouv.fr/formulaire/2759-sd/declaration-de-cessions-de-droits-sociaux-non-constatees-par-un-acte
- FEC structure: https://www.legifrance.gouv.fr/loda/article_lc/JORFARTI000027788280
- FEC guidance: https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant%3DBOI-CF-IOR-60-40-20-20170607
