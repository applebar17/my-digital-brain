# AI application states

## Purpose

This folder maps application-specific agentic capabilities onto the reusable AI
runtime framework. It distinguishes deterministic services/tools from LLM-only
and dynamic agentic states before concrete migration work begins.

## Contents

- [State and tool taxonomy with current map](state-and-tool-taxonomy.md):
  terminology, invocation patterns, the `query_memory` example, target
  classification of current capabilities, and required state documentation.

## Status

This is the application-integration layer of the clean-slate documentation.
Prompt templates and toolbox registration/management are deliberately not
specified here; they are the next design topic and will extend this map once
accepted.
