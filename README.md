
# RegInsight Copilot Demo

**Purpose:** Showcase an end‑to‑end AI Agent Factory workload on Azure AI Foundry for financial‑services use cases
using *public* SEC EDGAR filings and market‑data feeds.  
The demo delivers a conversational **RegInsight Copilot** that can:

1. **Ingest & index** every new 10‑K / 10‑Q filing from EDGAR.
2. **Answer natural‑language questions** with GPT‑4‑Turbo + Retrieval‑Augmented Generation.
3. **Generate charts & PowerPoint** summaries on demand.
4. **Call the user** via the new Azure AI Voice 'Live' API (optional).
5. **Log full lineage & compliance** in Microsoft Purview.

## Folder Structure
```
reginsight_demo/
  ├─ agents/              # Foundry YAML definitions
  ├─ notebooks/           # Python scripts (can be loaded as notebooks)
  ├─ dataflow/            # Dataflow Gen2 JSON
  ├─ terraform/           # IaC deployment (main.tf, variables.tf)
  ├─ bicep/               # Alternative Bicep template
  ├─ demo_script.md       # 5‑minute walkthrough
  └─ README.md            # This file
```

## Quick Start (High‑Level)

1. Deploy core resources with **Terraform** or **Bicep** (search, Purview, storage, OpenAI, Foundry).
2. Upload the YAML in `agents/` to Azure AI Foundry workspace.
3. Run `notebooks/ingest_sec_filings.py` once to back‑fill recent filings; schedule via Foundry or
   Dataflow Gen2 pipeline in `dataflow/`.
4. Chat with the published *RegInsight Copilot*; ask for summaries, comparisons, or PPT slides.
5. Monitor lineage and data access in **Microsoft Purview**; observe metrics in **Fabric** dashboards.

See `demo_script.md` for the guided live demo.
