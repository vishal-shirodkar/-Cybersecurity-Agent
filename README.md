# 🔐 Cybersecurity AI Agent

A Claude-powered cybersecurity assistant that routes your security questions to the most relevant expert skill from a database of **754 curated cybersecurity skills**, then streams a grounded, actionable response backed by MITRE ATT&CK, NIST CSF, and D3FEND frameworks.

![Architecture Diagram](docs/architecture.svg)

---

## 📋 Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Agent](#running-the-agent)
- [Available Commands](#available-commands)
- [Example Queries](#example-queries)
- [Skill Coverage](#skill-coverage)
- [Reports](#reports)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## How It Works

```
Your Question
     │
     ▼
┌─────────────────────┐
│   Skill Router      │  Semantic search over 754 skills using
│   (ChromaDB + RAG)  │  local sentence-transformers embeddings
└─────────────────────┘
     │  Top 3 matching skills + relevance scores
     ▼
┌─────────────────────┐
│   Skill Loader      │  Loads full skill context from disk:
│                     │  SKILL.md, workflow, standards, template
└─────────────────────┘
     │  Grounded system prompt
     ▼
┌─────────────────────┐
│   Claude Sonnet     │  Streams a precise, framework-grounded
│   (Anthropic API)   │  response to your terminal
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Report Generator   │  Saves a markdown report with skill
│                     │  context, AI response, and checklist
└─────────────────────┘
     │
     ▼
./reports/{timestamp}_{skill_name}.md
```

Each skill includes:
- **YAML frontmatter** — name, domain, subdomain, tags, version
- **Workflow** — step-by-step procedure
- **Framework mappings** — MITRE ATT&CK, NIST CSF, D3FEND, NIST AI RMF
- **Report template** — ready-to-fill checklist
- **Standards reference** — deep framework citations

---

## Project Structure

```
SecAgentSkills/
│
├── cybersecurity-agent/          # ← Main agent (start here)
│   ├── agent.py                  # CLI entry point (ask / chat / build-index / list-skills)
│   ├── skill_loader.py           # Reads SKILL.md files from disk
│   ├── skill_index.py            # Builds & queries ChromaDB RAG index
│   ├── skill_router.py           # Routes queries to best matching skills
│   ├── report_generator.py       # Saves markdown reports per query
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Environment variable template
│   │
│   ├── Anthropic-Cybersecurity-Skills/   # ← Clone this yourself (see Installation)
│   ├── chroma_db/                        # ← Auto-generated vector index (gitignored)
│   └── reports/                          # ← Auto-generated query reports (gitignored)
│
├── src/security_agent/           # MCP backend service (advanced integration)
├── tests/                        # Unit tests
├── docker/                       # Dockerfile for containerised deployment
├── scripts/                      # Seed and sync utilities
└── copilot/                      # GitHub Copilot integration config
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or higher | Check: `python --version` |
| Git | Any recent version | Check: `git --version` |
| Anthropic API Key | — | Get one at [console.anthropic.com](https://console.anthropic.com) |
| Disk space | ~500 MB | For skills repo + ChromaDB index |
| Internet | Required first run | Downloads embedding model (~90 MB) |

> 💡 **No GPU required.** The embedding model (`all-MiniLM-L6-v2`) runs on CPU.

---

## Installation

### Step 1 — Clone this repository

```bash
git clone https://github.com/vishal-shirodkar/-Cybersecurity-Agent.git
cd -Cybersecurity-Agent
```

### Step 2 — Clone the skills database

```bash
cd cybersecurity-agent
git clone https://github.com/mukul975/Anthropic-Cybersecurity-Skills
```

> This downloads 754 skills across 45 security subdomains (~50 MB).

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `anthropic` | Claude API SDK |
| `chromadb` | Local vector database for RAG |
| `sentence-transformers` | Local embedding model (no API key needed) |
| `python-dotenv` | Loads API key from `.env` file |
| `pyyaml` | Parses YAML frontmatter in SKILL.md files |
| `click` | CLI framework |
| `rich` | Terminal formatting (colours, tables, panels) |

### Step 4 — Configure your API key

```bash
cp .env.example .env
```

Open `.env` in any text editor and replace the placeholder:

```env
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

> 🔑 Get your API key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)  
> 💰 New accounts receive $5 free credits (~500–1000 queries with Claude Sonnet)

### Step 5 — Build the skill index (one-time setup)

```bash
python agent.py build-index
```

This embeds all 754 skills into a local ChromaDB vector database.

| First run | Subsequent runs |
|---|---|
| ~1–3 minutes (downloads model + embeds) | < 2 seconds (loads from disk) |

**Expected output:**
```
────────────── Building Skill Index ──────────────
Repo   : ./Anthropic-Cybersecurity-Skills
ChromaDB: ./chroma_db

✓ Index built successfully.
```

---

## Configuration

All configuration is loaded from the `.env` file in `cybersecurity-agent/`:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults shown)
SKILLS_REPO_PATH=./Anthropic-Cybersecurity-Skills
CHROMA_DB_PATH=./chroma_db
```

You can also override settings per-command using CLI flags:

```bash
python agent.py --repo /custom/path/to/skills --top-k 5 ask "your question"
```

---

## Running the Agent

All commands are run from the `cybersecurity-agent/` directory.

### Single question

```bash
python agent.py ask "How do I investigate a ransomware infection?"
```

### Interactive chat mode

```bash
python agent.py chat
```

Type your question and press Enter. Type `exit` or press `Ctrl+C` to quit.

### Build or rebuild the index

```bash
python agent.py build-index          # build if not already built
python agent.py build-index --force  # force a full rebuild
```

### Browse available skills

```bash
python agent.py list-skills                        # all 754 skills
python agent.py list-skills --domain cloud         # filter by domain
python agent.py list-skills --domain malware
python agent.py list-skills --domain forensics
```

---

## Available Commands

```
python agent.py [OPTIONS] COMMAND [ARGS]

Options:
  --repo PATH        Path to the skills repo  [default: ./Anthropic-Cybersecurity-Skills]
  --chroma-db PATH   Path to ChromaDB storage [default: ./chroma_db]
  --model TEXT       Anthropic model to use   [default: claude-sonnet-4-20250514]
  --top-k INT        Number of candidate skills to retrieve [default: 3]

Commands:
  ask          Ask a single security question
  chat         Start an interactive REPL session
  build-index  Build (or rebuild) the ChromaDB skill index
  list-skills  List all available skills in the index
```

---

## Example Queries

```bash
# Incident Response
python agent.py ask "How do I investigate a ransomware infection?"
python agent.py ask "What are the steps for a phishing incident response?"
python agent.py ask "How do I contain a compromised Windows host?"

# Threat Hunting
python agent.py ask "How do I hunt for lateral movement in my network?"
python agent.py ask "Detect living-off-the-land binaries on Windows"
python agent.py ask "How do I identify credential dumping attempts?"

# Malware Analysis
python agent.py ask "How do I perform static analysis on a suspicious binary?"
python agent.py ask "Analyse a suspicious PowerShell script"
python agent.py ask "How do I sandbox an unknown executable safely?"

# Cloud Security
python agent.py ask "How do I detect compromised AWS IAM credentials?"
python agent.py ask "Audit my Azure storage account for misconfigurations"
python agent.py ask "How do I investigate a Kubernetes cluster breach?"

# Digital Forensics
python agent.py ask "How do I capture memory from a live Windows system?"
python agent.py ask "Recover deleted files from an NTFS volume"
python agent.py ask "How do I analyse Windows event logs for intrusion?"

# Vulnerability Management
python agent.py ask "How do I prioritise CVEs for patching?"
python agent.py ask "Perform a web application security assessment"
```

---

## Skill Coverage

**754 skills** across **45 subdomains**:

| Subdomain | Skills | Subdomain | Skills |
|---|---|---|---|
| cloud-security | 63 | soc-operations | 33 |
| threat-hunting | 56 | identity-access-management | 33 |
| threat-intelligence | 50 | container-security | 29 |
| network-security | 43 | security-operations | 28 |
| web-application-security | 42 | ot-ics-security | 28 |
| malware-analysis | 39 | api-security | 28 |
| digital-forensics | 37 | incident-response | 26 |
| vulnerability-management | 25 | penetration-testing | 20 |
| red-teaming | 24 | devsecops | 17 |
| zero-trust-architecture | 17 | endpoint-security | 17 |
| phishing-defense | 15 | cryptography | 15 |
| ransomware-defense | 13 | mobile-security | 13 |
| + 21 more subdomains | … | | |

Skills are sourced from the open-source [Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) repository (Apache-2.0 licence).

---

## Reports

Every query automatically saves a markdown report to:

```
cybersecurity-agent/reports/{YYYYMMDD_HHMMSS}_{skill_name}.md
```

Each report contains:

| Section | Content |
|---|---|
| Header | Skill name, domain, relevance score, timestamp |
| Query | Your original question |
| Skill Context | Description, when-to-use, prerequisites |
| AI Analysis | Claude's full response |
| Skill Template | Ready-to-fill checklist (if skill has one) |
| Framework Mappings | NIST CSF, MITRE ATT&CK, D3FEND references |
| Metadata | Model used, cosine distance, skill file path |

To skip saving a report:

```bash
python agent.py ask "your question" --no-report
python agent.py chat --no-report
```

---

## Troubleshooting

### `ANTHROPIC_API_KEY is not set`
```
✗ ANTHROPIC_API_KEY is not set.
```
→ Make sure you created `.env` (not just `.env.example`) and added your key.  
→ Make sure you are running commands from the `cybersecurity-agent/` directory.

---

### `FileNotFoundError: Skills repo not found`
```
✗ Could not load skill '...': Skills repo not found
```
→ Clone the skills repo first:
```bash
git clone https://github.com/mukul975/Anthropic-Cybersecurity-Skills
```

---

### `Index not found — building...` on every run
→ The `chroma_db/` folder was deleted or the index was never built.  
→ Run: `python agent.py build-index`

---

### `No module named 'sentence_transformers'`
→ Run: `pip install sentence-transformers>=2.7.0`

---

### `AuthenticationError`
→ Your API key is invalid or expired.  
→ Generate a new key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)

---

### Slow first query after restart
→ Normal — the embedding model (~90 MB) loads into memory on first use.  
→ Subsequent queries in the same session are instant.

---

## Security Notes

| Item | Status |
|---|---|
| API key storage | `.env` file only — never in source code |
| `.env` in git | ❌ Excluded by `.gitignore` |
| `chroma_db/` in git | ❌ Excluded (200MB+, rebuild locally) |
| Skills repo in git | ❌ Excluded (clone separately) |
| Reports in git | ❌ Excluded (personal output) |
| Hardcoded secrets | ✅ None in any source file |

> ⚠️ **Never share your `.env` file or paste your API key into chat, issues, or pull requests.**  
> If your key is ever exposed, rotate it immediately at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).

---

## Contributing

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/my-improvement`
3. Commit your changes: `git commit -m "Add: description of change"`
4. Push: `git push origin feature/my-improvement`
5. Open a Pull Request

---

## Licence

This project is released under the [MIT Licence](LICENSE).

Skills data sourced from [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) — Apache-2.0 licence.

> *This tool is for educational and defensive security purposes only.*
