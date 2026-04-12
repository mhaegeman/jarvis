---
title: "Owl-Listener / Designer Skills"
type: source
date_ingested: 2026-04-12
source_file: raw/owl-listener-designer-skills.md
source_url: https://github.com/Owl-Listener/designer-skills
tags: [
  github, open-source, ai-tooling, claude-code,
  ux-design, design-systems, design-research,
  interaction-design, prototyping, ui-design, ux-strategy,
  skills-library, designer-workflow, ai-agents,
  no-code, markdown-prompts
]
---

## Summary

Designer Skills is a curated library of Claude Code skills and commands built for UX/product designers. It organises AI-assisted design work into eight domains — design-ops, design-research, design-systems, designer-toolkit, interaction-design, prototyping-testing, ui-design, and ux-strategy — each with its own set of SKILL.md prompt files and slash-command wrappers.

The repo is structured so that designers can drop the skills directory into any Claude Code project and immediately access specialist prompts for tasks like running affinity diagrams, generating component specs, planning usability tests, or writing design rationale. There is no runtime code: every "skill" is a structured markdown prompt that instructs Claude how to behave for that specific design task.

The scope is comprehensive: 50+ individual skills covering everything from accessibility audits and design-token creation to journey maps, A/B test design, animation principles, and competitive analysis. Commands provide shortcut entry points (e.g., `/discover`, `/design-interaction`, `/audit-system`) that chain multiple skills together.

This repo signals a pattern of building domain-specific AI skill libraries on top of Claude Code — analogous to npm packages but for AI behaviour rather than code.

## Tech Stack

- **Platform:** Claude Code (skills system)
- **Format:** Markdown (SKILL.md, command .md files)
- **Language:** None (prompt-only, no programming language)
- **Dependencies:** Claude Code CLI

## Purpose

Enable UX/product designers to use Claude Code as an expert design collaborator — covering research, strategy, systems, interaction, and delivery — without writing any code.

## Key Points

- 8 design domains, 50+ SKILL.md files, ~15 slash commands.
- Covers every phase of the design lifecycle: discovery → strategy → design → system → ops → delivery.
- Design-research skills include affinity-diagram, card-sort-analysis, diary-study-plan, empathy-map, interview-script, jobs-to-be-done, journey-map, summarize-interview, usability-test-plan, user-persona.
- Design-systems skills include accessibility-audit, component-spec, design-token, documentation-template, icon-system, naming-convention, pattern-library, theming-system.
- Interaction-design skills include animation-principles, error-handling-ux, feedback-patterns, gesture-patterns, loading-states, micro-interaction-spec, state-machine.
- Demonstrates the "skills as packages" concept for Claude Code extensibility.

## Quotes

> No runtime code: every "skill" is a structured markdown prompt that instructs Claude how to behave for that specific design task.

## Connections

- [Claude Code](../entities/claude-code.md) — the platform this skill library is built on top of.
- [Claude Code Agent Design](../concepts/agentic-workflow-patterns.md) — designer-skills is a domain-specific application of the broader agent/skills pattern.
- [EduardPetraeus / Claude Code Quickstart](owl-listener-designer-skills.md) — similar pattern: opinionated Claude Code starter kit (though for developers).

## Questions Raised

- Is there a standard registry or marketplace for Claude Code skill libraries?
- How do these skills compose with sub-agents — can a single command chain multiple SKILL.md agents?
