# 📜 Project Behavior & Constraints

These rules are enforced globally to prevent regression and chaos in the VM.

## 1. 🛑 Strict Boundaries
- **No Path Invention**: Never create top-level directories. Stick to `/app/src` and `/app/data`.
- **No Library Pollution**: Do not install new Python libraries without explicit user consent.
- **No Module Modification**: Do not modify files in `/app/src/shared/` unless specifically requested.

## 2. 🔍 Context Priority
- **Mandatory Check**: Before starting any task, read `.agent/docs/project_context.md`.
- **Amensia Prevention**: If you feel "lost", re-read the Project Brain instead of guessing.

## 3. 🔐 Security & Permissions
- **Secrets Handling**: Always use `cat` command to read `/app/src/.env`.
- **No Hardcoding**: Never put keys or passwords in the code. Use `os.getenv`.

## 4. 🛠️ Development Style
- **Modular First**: Keep ETL modules independent.
- **Logging**: Use robust try/except blocks and log errors for long-running ETL processes.
- **No GUI**: All code must be CLI-based or API-first.
