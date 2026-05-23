# Langfuse AI Skill Installation

## Overview

The Langfuse AI skill has been successfully installed in this workspace. This skill enables AI coding assistants to work with [Langfuse](https://langfuse.com) - the open-source LLM engineering platform for tracing, prompt management, and evaluation.

## Installation Details

- **Repository**: https://github.com/langfuse/skills
- **Installation Date**: 2026-05-23
- **Installation Location**: `.zoo-skills/langfuse/`
- **Installation Method**: Manual symlink from cloned repository

## Skill Capabilities

The Langfuse skill provides the following capabilities:

1. **Query and manage Langfuse data** via CLI:
   - Traces, prompts, datasets, scores, sessions
   - Full REST API access through `langfuse-cli`

2. **Access Langfuse documentation**:
   - Look up integration guides
   - SDK usage examples
   - Best practices and concepts

3. **Common workflows**:
   - Instrumenting applications with Langfuse tracing
   - Migrating prompts to Langfuse prompt management
   - Debugging traces and error analysis
   - Capturing user feedback as scores
   - Judge calibration and evaluation

## Prerequisites

To use the Langfuse skill, you need:

1. **Langfuse Account**: Either [cloud](https://cloud.langfuse.com) or [self-hosted](https://langfuse.com/docs/deployment/self-host)

2. **API Keys**: Set the following environment variables:
   ```bash
   export LANGFUSE_PUBLIC_KEY=pk-lf-...
   export LANGFUSE_SECRET_KEY=sk-lf-...
   export LANGFUSE_HOST=https://cloud.langfuse.com  # or https://us.cloud.langfuse.com for US cloud
   ```

   API keys can be found in Langfuse UI → **Settings → API Keys**

3. **Node.js/npm** (optional): For using the `langfuse-cli` tool via `npx`

## Skill Structure

```
.zoo-skills/langfuse/
├── SKILL.md                          # Main skill definition
└── references/
    ├── cli.md                        # CLI usage tips
    ├── error-analysis.md             # Systematic error analysis
    ├── instrumentation.md            # Application instrumentation guide
    ├── judge-calibration.md          # LLM-as-a-Judge calibration
    ├── prompt-migration.md           # Prompt migration workflows
    ├── sdk-upgrade.md                # SDK upgrade guide
    ├── skill-feedback.md             # Skill feedback process
    └── user-feedback.md              # User feedback capture

```

## Usage

Once installed, AI coding assistants will automatically use this skill when:

- Setting up Langfuse tracing in a project
- Auditing existing instrumentation
- Migrating prompts to Langfuse prompt management
- Querying traces, prompts, or datasets via the API
- Looking up Langfuse docs, SDK usage, or integration guides

## Core Principles

The skill follows these principles:

1. **Documentation First**: Always fetch current docs before implementing (Langfuse updates frequently)
2. **CLI for Data Access**: Use `langfuse-cli` when querying/modifying Langfuse data
3. **Best Practices by Use Case**: Check relevant reference files for use-case-specific guidelines
4. **Use Latest Versions**: Always use the latest version of Langfuse SDKs/APIs unless specified otherwise

## Next Steps

To integrate Langfuse tracing into the `gedcom-generation-microservice`:

1. Set up Langfuse API keys in the environment
2. Install the Langfuse Python SDK: `pip install langfuse`
3. Instrument the OpenRouter client and GEDCOM generation service
4. Configure trace metadata and user feedback capture

## Documentation

- **Langfuse Documentation**: https://langfuse.com/docs
- **Skills Repository**: https://github.com/langfuse/skills
- **Langfuse GitHub**: https://github.com/langfuse/langfuse

## Maintenance

The skill is symlinked from `/tmp/langfuse-skills/`. To update:

```bash
cd /tmp/langfuse-skills
git pull origin main
```

The changes will be immediately reflected in the workspace.
