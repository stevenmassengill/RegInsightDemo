
# 5‑Minute Live Demo Script — RegInsight Copilot

## Setup Preconditions
* Resources deployed via Terraform/Bicep (`rg`, Search, OpenAI, Storage, Purview, Foundry workspace).
* `ingest_sec_filings.py` has populated at least a handful of filings.
* Agents published in Foundry and front‑end (Copilot Studio or Streamlit) is live.

## Walkthrough (Timing ~5 minutes)

| Time | Action | Expected Screen / Output |
|------|--------|--------------------------|
| 0:00 | Share browser tab with **RegInsight Copilot** chat UI. | Shows welcome message. |
| 0:15 | Type: `"Summarize JPMorgan’s new risk factors in its latest 10‑K"` | Agent responds within ~5‑8 s with bullet list. Citations link to exact filing text hosted on SEC. |
| 1:00 | Ask follow‑up: `"Compare Wells Fargo’s Tier 1 Capital ratio to JPM and Citi for 2023."` | Copilot queries embedded docs + live price feed, returns paragraph + inline data table. |
| 2:00 | Click **"Create Board Slide"** custom command. | Behind scenes, ReportWriterAgent builds PPT; download link appears (`BoardUpdate_JPM_vs_WFC.pptx`). |
| 3:00 | Show Purview lineage view in another tab. | Highlights: ingest → OneLake → embeddings → Foundry response, proving auditability. |
| 3:30 | Switch to Fabric Power BI dashboard. | Live metrics: query count, avg latency, top companies queried. |
| 4:00 | Dial demo phone number (Twilio / Azure Communication Services) connected to VoiceAgent. | Caller hears synthesized voice reading last answer; ask a question verbally, AI replies in real‑time. |
| 5:00 | End with slide of KPI impact examples (fraud, compliance, advisor productivity). | Transition to Q&A. |

**Key Talking Points**  
* Entire pipeline built on Microsoft Build 2025 innovations: multi‑agent orchestration, Voice “Live” API, Entra Agent ID.  
* Purely public data → zero client data risk.  
* Modular: swap in ESG reports, climate data, or private loan docs with same architecture.  
* Governance first — every action traceable via Purview & Entra.  
* Time to value: first agent live in <2 hours.

## Cleanup
* Delete resource group or use Terraform destroy to avoid charges (<$50/month if left running).
