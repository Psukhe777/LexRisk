# 🏛️ RiskLex: AI-Powered Contract Intelligence

> **"Nobody reads the Terms of Service. Until now."**

RiskLex is an AI-driven legal analysis engine that scans, parses, and translates complex Terms of Service (ToS) and enterprise contracts into plain English. It instantly flags predatory clauses, data-harvesting policies, and hidden liabilities using advanced LLM reasoning.

🚀 **Status:** Day 5 Development — Part of the **"6 Startups in 60 Days"** Challenge.

---

## ⚡ The Day 5 Milestone: Velocity & Validation
Built for extreme speed and accuracy, RiskLex bypasses traditional week-long product validation cycles. By Day 5, we have achieved:
1. **Synthetic Market Validation:** Utilizing AI personas to run 10-minute multi-agent stress tests on the core logic.
2. **Cloud Deployment:** Live continuous integration via Streamlit Community Cloud.
3. **Core Engine Locked:** Full integration of Llama-3-70B for zero-latency legal parsing.

## 🛠️ The Tech Stack
RiskLex is built on a modern, high-speed Python architecture optimized for immediate deployment.

* **Frontend & Hosting:** Streamlit (v1.35.0) for rapid UI iteration and Community Cloud deployment.
* **The "Brain" (LLM):** Groq API powering **Llama-3-70B** for lightning-fast, highly contextual contract reasoning.
* **Document Processing:** `pypdf2` and `pdfplumber` for robust text extraction from complex legal PDFs.
* **NLP & Vectorization:** `sentence-transformers` and `scikit-learn` for semantic chunking and clause matching.
* **Testing:** `pytest` for integration and unit testing of the API logic.

## ⚙️ Core Features
* **Predatory Clause Detection:** Automatically identifies and scores high-risk language (e.g., auto-renewals, data selling, liability waivers).
* **Risk Heatmap:** Generates an overall "Risk Score" out of 100 for any pasted text or uploaded document.
* **Plain English Translation:** Strips away the legalese and explains exactly how a flagged clause impacts the user.



## 💻 Local Setup & Installation

If you want to run the RiskLex engine locall
