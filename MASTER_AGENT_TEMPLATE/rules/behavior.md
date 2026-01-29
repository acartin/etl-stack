# 📜 Universal Behavior & Constraints

These rules apply to ALL projects in this VM environment to ensure safety and order.

## 1. 🛑 Strict Boundaries
- **No Path Invention**: Never create top-level directories. Stick to the project structure defined in `project_context.md`.
- **No Library Pollution**: Do not install new Python/System libraries without explicit user consent.
- **Protected Zones**: Do not modify shared utilities or core configuration unless specifically requested.

## 2. 🔍 Context Priority
- **Mandatory Check**: Before starting any task, read `.agent/docs/project_context.md`.
- **Source of Truth**: If information in a conversation contradicts the Project Brain, the Project Brain WINS.

## 3. 🔐 Security & Operations
- **Secrets Protocol**: Never hardcode keys. Read `.env` files using safe terminal commands (like `cat`).
- **No GUI**: All code must be CLI-based or API-first. No `plt.show()` or windows.

## 4. 🛠️ Development Style
- **Modular Code**: Prefer small, independent modules over monolithic files.
- **Robustness**: Implement logs and error handling for all long-running processes (ETLs, Workers).
