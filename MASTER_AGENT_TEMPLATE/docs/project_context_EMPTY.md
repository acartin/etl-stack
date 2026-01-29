# 🧠 Project Brain: [PROJECT NAME]

This file is the **Source of Truth** for the project. Fill in the gaps to ensure the AI has perfect context.

## 🏗️ Infrastructure & Environment
- **OS/Container**: [e.g. Debian 12 / LXC #ID]
- **Hostname**: [e.g. prd-app-01]
- **Network/IP**: [e.g. 192.168.0.XX]
- **Virtual Env**: [Path to venv or 'system-wide']

## 📂 Filesystem Strategy
Define where the data lives and what each folder is for.

| Path | Hardware | Purpose |
| :--- | :--- | :--- |
| `/app/src` | [SSD/HDD] | [Main application code] |
| `/app/staging` | [SSD/NVMe] | [Temporary / Hot data] |
| `/app/storage` | [HDD] | [Permanent / Cold data] |

## 🐍 Software Stack & State
- **Critical Libraries**: [e.g. FastAPI, Pandas, DuckDB]
- **Database**: [Engine, Host, DB Name]
- **Secrets**: Located at [Absolute path to .env]
  - ⚠️ **Access Rule**: [e.g. Always use 'cat' via terminal]

## 🚀 The Mission
What is this specific project building? 
1. [Goal A]
2. [Goal B]

## 🛠️ Operations
- **Working Directory**: [Absolute path]
- **Execution**: [Command to run the main app]
- **Services**: [List of systemd services if any]
