"""
demo_data.py
Pre-computed contract analysis for instant sidebar demos.
Aligned with the Lexrisk 'Ruthless Lawyer' scoring matrix.
"""

DEMOS = {
  "x_tos": {
    "title": "Demos/X Tos",
    "text": "Terms of Service \nSummary of our Terms \nThese Terms of Service (“Terms”) are part of the User Agreement – a legally binding \ncontract governing your relationship with X... [Text Truncated for Demo] ...our aggregate liability \nshall not exceed the greater of $100 USD or the amount you paid us, if any, in the past six \nmonths for the Services giving rise to the claim.",
    "analysis": {
      "risk_score": 85,
      "risk_level": "HIGH",
      "flagged_clauses": [
        {
          "clause_text": "We provide the Services on an \"AS IS\" and \"AS AVAILABLE\" basis, and we disclaim all warranties, responsibility, and liability to you or others to the extent permitted by law.",
          "category": "Broad Indemnification / Waiver",
          "severity": "HIGH",
          "plain_english": "The company takes zero responsibility if their platform damages your device, business, or reputation.",
          "red_flag": "Complete waiver of service guarantees."
        },
        {
          "clause_text": "our aggregate liability shall not exceed the greater of $100 USD or the amount you paid us, if any, in the past six months for the Services giving rise to the claim.",
          "category": "Severe Limitation of Liability",
          "severity": "CRITICAL",
          "plain_english": "If the company's negligence costs you millions, the maximum you can sue them for is $100.",
          "red_flag": "Absurdly low liability cap ($100)."
        },
        {
          "clause_text": "You provide us with a broad, royalty-free license to make your Content available to the rest of the world and to let others do the same.",
          "category": "Perpetual Licensing / IP Rights",
          "severity": "MEDIUM",
          "plain_english": "You still own your content, but you give them the right to use, sell, or distribute it globally without paying you a dime.",
          "red_flag": "Broad, royalty-free IP license."
        }
      ],
      "summary": "This contract heavily insulates X from any legal or financial responsibility. By capping liability at $100 and taking a broad, free license to your intellectual property, the risk is entirely transferred to the user.",
      "recommendation": "NEGOTIATE"
    }
  },
  "tiktok": {
    "title": "Demos/Tiktok Tos",
    "text": "Tiktok\n\nTerms of Service\n\nLast updated: January 22, 2026\n\nWelcome to TikTok... [Text Truncated for Demo] ...YOU AND TIKTOK USDS JOINT VENTURE AGREE THAT YOU MUST INITIATE ANY PROCEEDING OR ACTION WITHIN ONE (1) YEAR OF THE DATE OF THE OCCURRENCE OF THE EVENT...",
    "analysis": {
      "risk_score": 95,
      "risk_level": "CRITICAL",
      "flagged_clauses": [
        {
          "clause_text": "We may remove or restrict access to any content, including yours, whether publicly or privately posted, for any reason...",
          "category": "Termination for Convenience",
          "severity": "HIGH",
          "plain_english": "They can delete your account, your audience, and your business on their platform at any time, without giving you a reason.",
          "red_flag": "Account termination without cause."
        },
        {
          "clause_text": "YOU AND TIKTOK USDS JOINT VENTURE AGREE THAT YOU MUST INITIATE ANY PROCEEDING OR ACTION WITHIN ONE (1) YEAR OF THE DATE OF THE OCCURRENCE OF THE EVENT...",
          "category": "Statute of Limitations Reduction",
          "severity": "CRITICAL",
          "plain_english": "You are giving up your legal right to the standard statute of limitations, giving you only 12 months to realize you were wronged and file a lawsuit.",
          "red_flag": "Drastic reduction of your right to sue."
        },
        {
          "clause_text": "Any claim, cause of action or dispute... shall also be resolved exclusively in the U.S. District Court for the Central District of California...",
          "category": "Inconvenient Venue",
          "severity": "HIGH",
          "plain_english": "If you want to sue them, you are forced to travel to California and hire a California-licensed attorney to do so.",
          "red_flag": "Forces out-of-state litigation."
        }
      ],
      "summary": "A highly predatory social media contract. It artificially reduces your window to take legal action to one year, forces all lawsuits to happen in California, and grants the company the right to terminate your account without cause.",
      "recommendation": "AVOID"
    }
  },
  "gym": {
    "title": "Demos/Gym Agreement",
    "text": "Last updated: 11/10/22\n\nThese Website Terms and Conditions of Use... [Text Truncated for Demo] ...BE RESOLVED EXCLUSIVELY BY BINDING ARBITRATION BEFORE THE AMERICAN ARBITRATION ASSOCIATION... THIS MEANS NEITHER YOU NOR THE PLANET FITNESS PARTIES MAY JOIN CLAIMS IN ARBITRATION WITH OR AGAINST OTHER USERS...",
    "analysis": {
      "risk_score": 92,
      "risk_level": "CRITICAL",
      "flagged_clauses": [
        {
          "clause_text": "BE RESOLVED EXCLUSIVELY BY BINDING ARBITRATION BEFORE THE AMERICAN ARBITRATION ASSOCIATION...",
          "category": "Binding Arbitration",
          "severity": "CRITICAL",
          "plain_english": "You are signing away your constitutional right to a trial by a judge or jury. You must settle disputes in private arbitration, which heavily favors the corporation.",
          "red_flag": "Strips your right to a jury trial."
        },
        {
          "clause_text": "THIS MEANS NEITHER YOU NOR THE PLANET FITNESS PARTIES MAY JOIN CLAIMS IN ARBITRATION WITH OR AGAINST OTHER USERS, OR LITIGATE IN COURT OR ARBITRATE ANY CLAIMS AS A REPRESENTATIVE OR MEMBER OF A CLASS.",
          "category": "Class Action Waiver",
          "severity": "CRITICAL",
          "plain_english": "If the gym illegally overcharges 100,000 members, you cannot band together to sue them. You must fight them individually, making it financially impossible.",
          "red_flag": "Prevents class-action lawsuits."
        },
        {
          "clause_text": "unsolicited information and content submitted to this Site is assigned to Planet Fitness free of charge, together with all worldwide rights...",
          "category": "Perpetual Licensing / IP Theft",
          "severity": "HIGH",
          "plain_english": "Any idea, feedback, or content you submit to their site instantly becomes their property without them paying you.",
          "red_flag": "Uncompensated intellectual property assignment."
        }
      ],
      "summary": "This contract contains the two most dangerous clauses in modern consumer law: Binding Arbitration and a Class Action Waiver. By signing this, you completely surrender your ability to hold the company accountable in a court of law.",
      "recommendation": "AVOID"
    }
  },
  "nda": {
    "title": "Demos/Nda Agreement",
    "text": "NON-DISCLOSURE AGREEMENT (NDA)...",
    "analysis": {
      "risk_score": 15,
      "risk_level": "LOW",
      "flagged_clauses": [
        {
          "clause_text": "Receiving Party shall return to Disclosing Party any and all records, notes, and other written, printed, or tangible materials in its possession pertaining to Confidential Information immediately if Disclosing Party requests it in writing.",
          "category": "Data Destruction / Return",
          "severity": "LOW",
          "plain_english": "You must immediately delete or return all confidential data the moment they ask for it, which is a standard security protocol.",
          "red_flag": "Strict document return policy."
        }
      ],
      "summary": "This is a highly standard, mutual Non-Disclosure Agreement. It contains fair exclusions for public knowledge and includes the standard federal immunity clause for whistleblowers. There are no predatory traps here.",
      "recommendation": "SIGN"
    }
  }
}
