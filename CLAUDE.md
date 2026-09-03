# SPIDY — Claude Code Instructions

## Project

SPIDY is a personal AI computer-use assistant for Windows.

Read these files before making significant changes:

- PRODUCT_VISION.md
- DEVELOPMENT_PLAN.md
- README.md
- CHANGELOG.md if it exists

## Development Rules

- Inspect the existing code before modifying it.
- Never delete or overwrite working functionality without explaining why.
- Follow DEVELOPMENT_PLAN.md.
- Implement only the current phase unless explicitly instructed otherwise.
- Keep the architecture modular and extensible.
- Prefer simple implementations before complex ones.
- Minimize dependencies.
- Write tests for important functionality.
- Run tests after changes.
- Report errors honestly.

## Security

The LLM is NOT the security boundary.

Every tool must have an application-enforced permission level.

Possible levels:

- SAFE
- CONFIRM
- HIGH_RISK
- BLOCKED

Never allow the model to bypass the permission system.

Validate all tool inputs.

Restrict filesystem access.

Prevent path traversal.

Do not expose secrets to the model unnecessarily.

Do not store API keys, passwords, tokens or credentials in source code.

Never commit .env files.

## Computer Control

Prefer:

1. Direct APIs
2. Structured application interfaces
3. Windows UI Automation
4. Browser automation
5. Visual/screen automation only when necessary

Do not rely on screen coordinates when a reliable structured interface exists.

## Dangerous Actions

The following generally require confirmation:

- File deletion
- System changes
- Software installation
- Sending email/messages
- Git push
- Destructive shell commands
- Credential-related operations
- External submissions

## Workflow

Before implementation:

1. Inspect the project.
2. Identify the current phase.
3. Explain the planned changes.
4. Implement the smallest correct change.
5. Run tests.
6. Check for security problems.
7. Update documentation.
8. Update CHANGELOG.md.
9. Report what changed.

After a milestone is stable, recommend a Git commit.

## Important

Do not assume previous chat history exists.

The project files are the source of truth.