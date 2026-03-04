# demo_data.py
# Pure data store for instant demos. No logic or imports allowed here.

DEMOS = {
  "tiktok": {
    "title": "TikTok Terms of Service",
    "text": "Tiktok\n\nTerms of Service\n\n\nLast updated: January 22, 2026...", # (Keep your full 41k character text here)
    "analysis": {
      "risk_score": 72,
      "risk_level": "HIGH",
      "flagged_clauses": [
        {
          "clause_text": "You grant us and our affiliates, service providers...",
          "category": "Intellectual Property",
          "severity": "CRITICAL",
          "plain_english": "TikTok can use, modify, and sell your content forever...",
          "red_flag": "Perpetual, irrevocable license with no compensation"
        }
        # ... (Keep your other TikTok clauses here)
      ],
      "summary": "TikTok's terms grant them extremely broad rights...",
      "recommendation": "AVOID"
    }
  },
  "x_tos": {
      # ... (Keep your X, Gym, and NDA data exactly as it was)
  }
}
