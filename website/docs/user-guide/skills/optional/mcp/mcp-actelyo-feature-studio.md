---
title: "Actelyo Feature Studio — Turn authorized app analysis into tested Actelyo features"
sidebar_label: "Actelyo Feature Studio"
description: "Turn authorized app analysis into tested Actelyo features"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Actelyo Feature Studio

Turn authorized app analysis into tested Actelyo features.

## Skill metadata

| | |
|---|---|
| Source | Optional — install with `hermes skills install official/mcp/actelyo-feature-studio` |
| Path | `optional-skills/mcp/actelyo-feature-studio` |
| Version | `1.0.0` |
| Author | Jeanne Retsamy (@jeanneretsamy-ux) and Hermes Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `REA`, `MCP`, `Actelyo`, `coding`, `Electron` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Actelyo Feature Studio

Use REA to understand a feature in software the user is authorized to inspect, then build an original implementation in the selected Actelyo code workspace. This skill guides analysis and coding; it does not copy the reference application's source, assets, branding, or protected data.

## When to Use

- The user wants to understand one behavior in an application such as LM Studio.
- The user wants to implement a comparable, Actelyo-specific capability in a selected repository.
- The work needs evidence from a local JavaScript/Electron application before code changes.

## Prerequisites

- Connect and enable the `rea` MCP server from Law Harness Connectors. For a locally installed reference app, use a local Law Harness backend; an SSH or cloud backend cannot read files that exist only on this PC.
- Install this optional skill from **Skills → MCP → Actelyo Feature Studio**.
- Open the Actelyo repository or feature workspace in Law Harness so its coding tools can read, edit, and test that project.
- The first REA connection downloads its pinned npm package and needs internet access. REA's static JavaScript/Electron analysis needs no native analysis engine.

## How to Run

Describe the reference application, the specific behavior to study, and the Actelyo workspace where the result belongs. Example: “Analyze how LM Studio selects a local model, then propose and implement an Actelyo-specific model selector in this workspace.”

## Quick Reference

| Goal | REA tool |
|---|---|
| Check the active session and available operations | `binary_session` |
| Analyze a local JavaScript/Electron app | `analyze_javascript_application` |
| Read a focused view of retained analysis evidence | `inspect_analysis_view` |
| Trace a feature through an analyzed application | `trace_application_feature` |

Use the actual input schema and availability reported by the connected `rea` server. Do not invent paths, parameters, or operations.

## Procedure

1. Confirm the exact feature and the local app path with the user. Inspect only software they own or are authorized to analyze. If the app or requested feature is ambiguous, ask which one to use.
2. Call `binary_session` to check the connected REA version and which operations are available. For an Electron or JavaScript app, call `analyze_javascript_application` on the user-selected application directory or ASAR. Use `inspect_analysis_view` or `trace_application_feature` for a focused follow-up when the evidence supports it.
3. Report what REA observed, what is an inference, and what remains unknown. Static analysis does not prove runtime behavior. Do not repeat the same analysis unless the target or unanswered question changes.
4. Before editing, inspect the selected workspace with `search_files`, `read_file`, and `terminal`; check its instructions, current changes, UI conventions, and tests. Keep all edits inside that workspace and preserve existing user changes.
5. Turn the observed behavior into an Actelyo-native design: use Actelyo naming, layout, data contracts, and legal-workspace boundaries. Do not copy the target's source, proprietary assets, private APIs, credentials, or exact branded presentation.
6. Implement the smallest useful feature with `patch` and `write_file`. Keep it separate from client dossier contents. Do not install packages, download models, alter global machine settings, or connect to legal data as an implementation shortcut.
7. Run the relevant tests and build available in the selected project using `terminal`. Review the final diff and report files changed, tests run, evidence used, and any remaining manual checks. Leave merge, release, or deployment to an explicit user request.

## Pitfalls

- REA's MCP process runs where the Hermes backend runs. A remote backend cannot inspect an application stored only on the user's computer.
- An analysis report is evidence about the examined files, not proof that the application behaved that way at runtime.
- Deep native analysis may need a separately installed provider. Do not install Hopper, Ghidra, or other analysis software as part of ordinary JavaScript/Electron analysis.
- A feature that resembles a reference must still fit Actelyo's own interaction and legal-data boundaries.

## Verification

- Confirm the selected REA tools were available and cite the returned evidence identifiers in the work summary when present.
- Run the project's relevant tests/build and inspect the diff with `terminal` before describing the feature as implemented.
- Mark runtime behavior, packaging, and deployment as unverified until each is actually exercised.
