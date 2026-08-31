# LexRisk

**Contract Risk Intelligence**

LexRisk scans, parses, and analyzes legal contracts and Terms of Service 
documents using a multi-layer AI pipeline — flagging liability exposure, 
predatory clauses, TCPA compliance issues, and jurisdiction-specific risk 
before you sign.

Built for individuals, freelancers, and businesses who sign contracts 
they cannot afford to have reviewed by an attorney at $300/hour.

---

## What It Does

- **Risk Scoring** — Overall risk score out of 100 with clause-level 
  breakdown
- **Predatory Clause Detection** — Auto-renewal traps, data-selling 
  provisions, liability waivers, indemnification exposure
- **Jurisdictional Analysis** — Rule engine covers Federal baseline plus 
  state-specific variations
- **Liability Calculation** — Quantified exposure estimates per flagged 
  clause
- **Clause Rewriting** — Generates compliant alternative language for 
  high-risk provisions
- **Contract Redlining** — Tracked changes output for negotiation
- **Bulk Processing** — Batch analysis for teams reviewing multiple 
  contracts
- **PDF Export** — Structured risk report generation
- **Attorney Routing** — Email routing for escalation to legal counsel

---

## Tech Stack

- **Frontend:** Streamlit with custom theming
- **LLM:** Groq API — Llama-3-70B for contract reasoning
- **NLP:** sentence-transformers, scikit-learn for semantic clause matching
- **Document Processing:** pypdf2, pdfplumber for PDF extraction with 
  OCR fallback
- **Resilience:** Circuit breaker pattern, rate limiting, health checks
- **Telemetry:** Usage analytics and performance monitoring
- **Database:** PostgreSQL via Railway (schema in schema.sql)
- **Testing:** pytest — unit and integration coverage

---

## Architecture
main.py → Entry point, jurisdiction resolution
analyzer.py → Core analysis engine
nlp_engine.py → Semantic clause matching
jurisdictional_rules.py → Multi-jurisdiction rule engine
liability_calculator.py → Exposure quantification
clause_rewriter.py → Compliant language generation
redliner.py → Contract redlining output
bulk_processor.py → Batch processing
ocr_processor.py → PDF text extraction
pdf_export.py → Report generation
email_router.py → Attorney escalation routing
circuit_breaker.py → Fault tolerance
rate_limiter.py → Usage control
telemetry.py → Analytics
health_check.py → System monitoring


---

## Deployment

Deployed on Railway. Connects to PostgreSQL for persistent storage.

```bash
# Local development
pip install -r requirements.txt
streamlit run main.py
```

Environment variables required — see `.env.example`.

---

## Status

v2.0 live at [lexrisk.babylontechnologies.org](https://lexrisk.babylontechnologies.org)

open source under MIT license. v2.0 is a proprietary commercial 
release with tiered pricing.

---

## License

v1.0: MIT License — see LICENSE file.

v2.0 commercial features (bulk processing, attorney routing, redlining, 
jurisdiction engine) are proprietary. Contact 
nehemiahsturdivant@babylontechnologies.org for licensing.

---

**Disclaimer:** LexRisk is an AI analysis tool, not a substitute for 
legal advice. Always consult a qualified attorney before making decisions 
based on this analysis.

Built by Nehemiah Sturdivant — Babylon Technologies LLC
Made By Nehemiah// Babylon Technologies LLC 
