"""
nlp_engine.py — Deterministic NLP Vectorization Engine
Purpose: Pre-filter contracts using semantic similarity to reduce LLM API latency by 80%
Features:
- 100-clause predatory legal pattern library
- sentence-transformers embeddings (all-MiniLM-L6-v2)
- Cosine similarity matching with configurable thresholds
- Memory-efficient chunking and batch processing
"""

import logging
import json
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PREDATORY CLAUSE LIBRARY (100 Known Patterns)
# ══════════════════════════════════════════════════════════════════════════════

PREDATORY_CLAUSE_LIBRARY = [
    # ── Arbitration & Class Action Waivers (15) ──
    {"category": "Arbitration", "severity": "HIGH", "text": "You agree to resolve any disputes through binding arbitration and waive your right to participate in class action lawsuits."},
    {"category": "Arbitration", "severity": "HIGH", "text": "All claims must be brought in individual arbitration and you waive the right to a jury trial."},
    {"category": "Arbitration", "severity": "CRITICAL", "text": "By using this service, you waive your right to sue in court and agree to mandatory arbitration with limited discovery."},
    {"category": "Arbitration", "severity": "HIGH", "text": "You agree that arbitration will be conducted by a single arbitrator selected by the company."},
    {"category": "Arbitration", "severity": "CRITICAL", "text": "This agreement contains a mandatory arbitration provision that requires you to resolve disputes on an individual basis through arbitration."},
    {"category": "Arbitration", "severity": "HIGH", "text": "You expressly waive the right to a trial by jury and the right to participate as a plaintiff or class member in any class action."},
    {"category": "Arbitration", "severity": "HIGH", "text": "Any dispute arising from this agreement shall be resolved exclusively through binding arbitration under the rules of the American Arbitration Association."},
    {"category": "Arbitration", "severity": "CRITICAL", "text": "You agree to arbitrate all disputes and waive any right to bring claims in a representative capacity."},
    {"category": "Arbitration", "severity": "HIGH", "text": "The arbitrator's decision shall be final and binding, and judgment may be entered in any court of competent jurisdiction."},
    {"category": "Arbitration", "severity": "CRITICAL", "text": "You waive your right to participate in class arbitration or any form of consolidated or collective action."},
    {"category": "Arbitration", "severity": "HIGH", "text": "Disputes will be resolved through individual arbitration, and you waive the right to have a court or jury decide your claim."},
    {"category": "Arbitration", "severity": "HIGH", "text": "You agree that any arbitration will be administered by an arbitration organization chosen by us."},
    {"category": "Arbitration", "severity": "CRITICAL", "text": "This arbitration agreement survives termination of your account and applies to claims that arose before or after this agreement."},
    {"category": "Arbitration", "severity": "HIGH", "text": "You agree to waive any right to bring claims on behalf of others or participate in any class or collective proceeding."},
    {"category": "Arbitration", "severity": "HIGH", "text": "Each party shall bear their own costs in arbitration unless the arbitrator determines otherwise."},
    
    # ── Unilateral Modification (10) ──
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "We reserve the right to modify these terms at any time without prior notice to you."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "We may change, suspend, or discontinue any aspect of the service at any time without liability."},
    {"category": "Unilateral Modification", "severity": "CRITICAL", "text": "We may modify pricing, features, or terms at our sole discretion, and continued use constitutes acceptance."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "The company reserves the right to update these terms without notice, and such changes will be effective immediately upon posting."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "We may amend this agreement at any time by posting the revised terms on our website."},
    {"category": "Unilateral Modification", "severity": "CRITICAL", "text": "We reserve the right to change fees, billing methods, or payment terms at any time without advance notice."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "These terms may be modified from time to time, and your continued access signifies acceptance of changes."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "We may revise these terms at our discretion and will notify you by posting the updated version."},
    {"category": "Unilateral Modification", "severity": "CRITICAL", "text": "The company may alter, suspend, or terminate any service feature without prior notification or liability."},
    {"category": "Unilateral Modification", "severity": "HIGH", "text": "We reserve the right to change the terms of service at any time, with or without notice to users."},
    
    # ── IP Rights & Content Licensing (12) ──
    {"category": "IP Rights", "severity": "CRITICAL", "text": "You grant us a perpetual, irrevocable, worldwide license to use, modify, and commercialize any content you upload."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "By submitting content, you grant us an unlimited, royalty-free license to use your content for any purpose."},
    {"category": "IP Rights", "severity": "HIGH", "text": "You grant us a non-exclusive, transferable, sublicensable license to use your content in connection with our services."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "Any content you create using our platform becomes our property and we may use it for commercial purposes."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "You hereby assign all intellectual property rights in your submissions to the company."},
    {"category": "IP Rights", "severity": "HIGH", "text": "You grant us the right to use your name, likeness, and submitted materials in our marketing and promotional activities."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "All user-generated content is owned by the company upon submission and may be used without attribution or compensation."},
    {"category": "IP Rights", "severity": "HIGH", "text": "You grant us a worldwide, perpetual license to reproduce, distribute, and create derivative works from your content."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "By uploading materials, you transfer all ownership rights to the company without any ongoing rights or royalties."},
    {"category": "IP Rights", "severity": "HIGH", "text": "You waive all moral rights and agree that we may modify your content without your permission or credit."},
    {"category": "IP Rights", "severity": "CRITICAL", "text": "Any ideas, feedback, or suggestions you provide become our exclusive property."},
    {"category": "IP Rights", "severity": "HIGH", "text": "You grant us the right to use your content in any media now known or hereafter developed without compensation."},
    
    # ── Auto-Renewal & Billing (10) ──
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "Your subscription will automatically renew unless you cancel at least 30 days before the renewal date."},
    {"category": "Auto-Renewal", "severity": "CRITICAL", "text": "You authorize us to automatically charge your payment method for recurring fees, and no refunds will be provided."},
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "Subscriptions automatically renew at the then-current rate, which may increase without prior notice."},
    {"category": "Auto-Renewal", "severity": "CRITICAL", "text": "By subscribing, you agree to automatic renewal and waive any right to cancel after the billing date."},
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "Your account will be charged automatically for the next billing period unless you cancel 60 days in advance."},
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "We will continue charging your payment method until you provide written cancellation notice."},
    {"category": "Auto-Renewal", "severity": "CRITICAL", "text": "You agree that we may change subscription fees at renewal without providing advance notice."},
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "All subscriptions auto-renew and you must cancel before the renewal date to avoid charges."},
    {"category": "Auto-Renewal", "severity": "HIGH", "text": "Your subscription renews automatically and we are not obligated to provide refunds for partial periods."},
    {"category": "Auto-Renewal", "severity": "CRITICAL", "text": "You authorize recurring charges and agree that cancellation requires 90 days advance notice."},
    
    # ── Limitation of Liability (10) ──
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "Our total liability to you for any damages is limited to the amount you paid in the last 30 days, not to exceed $50."},
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "In no event shall the company be liable for any damages exceeding $100, regardless of the cause of action."},
    {"category": "Limitation of Liability", "severity": "HIGH", "text": "We disclaim all warranties and limit our liability to the fees paid by you in the three months preceding the claim."},
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "The company's maximum liability is capped at $25 for any and all claims arising from your use of the service."},
    {"category": "Limitation of Liability", "severity": "HIGH", "text": "We shall not be liable for any indirect, incidental, or consequential damages under any circumstances."},
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "Our aggregate liability for all claims is limited to the lesser of $50 or the amount you paid in the last month."},
    {"category": "Limitation of Liability", "severity": "HIGH", "text": "The company disclaims all liability for data loss, service interruptions, or security breaches."},
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "You agree that our total liability shall not exceed $10 for any reason whatsoever."},
    {"category": "Limitation of Liability", "severity": "HIGH", "text": "We are not responsible for any damages and limit our liability to a refund of fees paid in the prior 30 days."},
    {"category": "Limitation of Liability", "severity": "CRITICAL", "text": "The maximum amount recoverable from the company is $20, regardless of the nature or extent of your damages."},
    
    # ── Termination & Account Control (8) ──
    {"category": "Termination", "severity": "HIGH", "text": "We may terminate your account at any time for any reason without notice or refund."},
    {"category": "Termination", "severity": "CRITICAL", "text": "The company reserves the right to suspend or delete your account immediately without cause and without providing a refund."},
    {"category": "Termination", "severity": "HIGH", "text": "We may discontinue your access to the service at our sole discretion without prior notification."},
    {"category": "Termination", "severity": "HIGH", "text": "Your account may be terminated immediately upon any violation of these terms, real or perceived."},
    {"category": "Termination", "severity": "CRITICAL", "text": "We retain the right to delete all your data and terminate your account without warning or compensation."},
    {"category": "Termination", "severity": "HIGH", "text": "The company may suspend or terminate services at any time without liability or obligation to provide refunds."},
    {"category": "Termination", "severity": "HIGH", "text": "We may close your account for convenience without providing reasons or returning unused subscription fees."},
    {"category": "Termination", "severity": "CRITICAL", "text": "Termination is effective immediately, and you forfeit all paid fees and access to your content."},
    
    # ── Indemnification (8) ──
    {"category": "Indemnification", "severity": "HIGH", "text": "You agree to indemnify and hold harmless the company from any claims arising from your use of the service."},
    {"category": "Indemnification", "severity": "CRITICAL", "text": "You shall defend, indemnify, and hold us harmless from all damages, costs, and attorney fees arising from your conduct."},
    {"category": "Indemnification", "severity": "HIGH", "text": "You agree to reimburse the company for any losses, liabilities, or expenses incurred due to your actions."},
    {"category": "Indemnification", "severity": "CRITICAL", "text": "You will indemnify us against all claims, including those arising from our own negligence or misconduct."},
    {"category": "Indemnification", "severity": "HIGH", "text": "You agree to compensate the company for any legal fees or damages resulting from third-party claims related to your use."},
    {"category": "Indemnification", "severity": "HIGH", "text": "You shall indemnify and defend the company against any claim, demand, or action brought by third parties."},
    {"category": "Indemnification", "severity": "CRITICAL", "text": "You agree to cover all costs, including attorney fees, if the company is sued due to your use of the service."},
    {"category": "Indemnification", "severity": "HIGH", "text": "You will hold the company harmless from any liability arising from your breach of this agreement or applicable law."},
    
    # ── Data & Privacy (8) ──
    {"category": "Data Sharing", "severity": "CRITICAL", "text": "We may share your personal information with third parties for marketing purposes without your explicit consent."},
    {"category": "Data Sharing", "severity": "CRITICAL", "text": "Your data may be sold or transferred to our business partners and affiliates for any commercial use."},
    {"category": "Data Sharing", "severity": "HIGH", "text": "We reserve the right to disclose your information to third parties at our discretion."},
    {"category": "Data Sharing", "severity": "CRITICAL", "text": "By using our service, you consent to the collection and sale of your personal data to advertisers and data brokers."},
    {"category": "Data Sharing", "severity": "HIGH", "text": "We may share your information with service providers, partners, and other entities as we deem necessary."},
    {"category": "Data Sharing", "severity": "CRITICAL", "text": "You grant us permission to use and monetize your personal data without restriction or compensation."},
    {"category": "Data Sharing", "severity": "HIGH", "text": "Your information may be transferred to third parties in connection with business transactions such as mergers or acquisitions."},
    {"category": "Data Sharing", "severity": "HIGH", "text": "We may disclose your data to law enforcement, government agencies, or private parties at our sole discretion."},
    
    # ── Non-Compete & Exclusivity (5) ──
    {"category": "Non-Compete", "severity": "CRITICAL", "text": "You agree not to use competing services or develop similar products for a period of 5 years after termination."},
    {"category": "Non-Compete", "severity": "CRITICAL", "text": "During and after the term, you shall not engage in any business that competes with our services."},
    {"category": "Non-Compete", "severity": "HIGH", "text": "You agree to exclusive use of our platform and may not use any competitor's services."},
    {"category": "Non-Compete", "severity": "CRITICAL", "text": "You shall not solicit our customers or employees for two years following termination of this agreement."},
    {"category": "Non-Compete", "severity": "HIGH", "text": "You agree not to develop, support, or assist with any competing product or service."},
    
    # ── Gag Clauses & Non-Disparagement (5) ──
    {"category": "Gag Clause", "severity": "CRITICAL", "text": "You agree not to make any negative or disparaging statements about the company publicly or privately."},
    {"category": "Gag Clause", "severity": "CRITICAL", "text": "You shall not write reviews, post comments, or discuss your experience with our service in any forum."},
    {"category": "Gag Clause", "severity": "HIGH", "text": "You agree to confidentiality regarding all aspects of this agreement and your use of the service."},
    {"category": "Gag Clause", "severity": "CRITICAL", "text": "You may not disclose any information about the company or this agreement to third parties without our written consent."},
    {"category": "Gag Clause", "severity": "HIGH", "text": "You agree not to publish or communicate any criticism, complaints, or negative feedback about our services."},
    
    # ── Venue & Governing Law (4) ──
    {"category": "Venue", "severity": "HIGH", "text": "Any disputes must be brought exclusively in the courts of Delaware, and you consent to personal jurisdiction there."},
    {"category": "Venue", "severity": "HIGH", "text": "This agreement shall be governed by the laws of the Cayman Islands, without regard to conflict of law principles."},
    {"category": "Venue", "severity": "CRITICAL", "text": "You agree that all legal actions must be filed in a specific court in a foreign jurisdiction at your own expense."},
    {"category": "Venue", "severity": "HIGH", "text": "Disputes shall be resolved in the courts of Ireland, and you waive any objection to this venue."},
    
    # ── Miscellaneous High-Risk (5) ──
    {"category": "Penalties", "severity": "CRITICAL", "text": "You agree to pay liquidated damages of $10,000 for each breach of this agreement."},
    {"category": "Survival", "severity": "HIGH", "text": "The IP license, indemnification, and limitation of liability provisions survive termination indefinitely."},
    {"category": "Audit Rights", "severity": "HIGH", "text": "The company may audit your systems and records at any time with 24 hours notice or less."},
    {"category": "Injunctive Relief", "severity": "CRITICAL", "text": "The company may seek injunctive relief without posting a bond to restrain any breach of this agreement."},
    {"category": "Penalties", "severity": "CRITICAL", "text": "You shall pay a penalty of $5,000 per day for any unauthorized use of the service."}
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ChunkMatch:
    """Represents a contract chunk matched to a predatory clause"""
    chunk_text: str
    matched_clause: str
    similarity_score: float
    category: str
    severity: str
    chunk_index: int


@dataclass
class NLPFilterResult:
    """Result from NLP pre-filtering"""
    high_risk_chunks: List[str]
    matched_clauses: List[ChunkMatch]
    total_chunks: int
    chunks_flagged: int
    max_similarity: float
    filter_ratio: float  # Percentage of text filtered out


# ══════════════════════════════════════════════════════════════════════════════
# NLP VECTORIZATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class NLPVectorizationEngine:
    """
    Deterministic semantic similarity engine for predatory clause detection.
    Uses sentence-transformers to match contract chunks against known patterns.
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.65,
        chunk_size: int = 3,  # sentences per chunk
        max_chunks_to_send: int = 50  # hard cap on chunks sent to LLM
    ):
        """
        Initialize NLP engine with embedding model and thresholds.
        
        Args:
            model_name: SentenceTransformer model identifier
            similarity_threshold: Minimum cosine similarity to flag a chunk (0-1)
            chunk_size: Number of sentences per chunk
            max_chunks_to_send: Maximum chunks to return for LLM processing
        """
        self.similarity_threshold = similarity_threshold
        self.chunk_size = chunk_size
        self.max_chunks_to_send = max_chunks_to_send
        
        logger.info(f"Initializing NLPVectorizationEngine with model: {model_name}")
        
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"✅ Model loaded: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise
        
        # Pre-compute embeddings for predatory clause library
        self._initialize_clause_library()
    
    def _initialize_clause_library(self) -> None:
        """Pre-compute embeddings for all predatory clauses (one-time cost)"""
        logger.info("Computing embeddings for 100-clause predatory library...")
        
        self.clause_texts = [clause["text"] for clause in PREDATORY_CLAUSE_LIBRARY]
        self.clause_metadata = [
            {"category": c["category"], "severity": c["severity"]}
            for c in PREDATORY_CLAUSE_LIBRARY
        ]
        
        # Compute embeddings in batch (efficient)
        self.clause_embeddings = self.model.encode(
            self.clause_texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        logger.info(f"✅ Library initialized: {len(self.clause_texts)} clauses embedded")
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split contract into sentence-based chunks.
        
        Strategy: Split by sentence boundaries, then group into chunks of N sentences.
        This preserves semantic context while remaining memory-efficient.
        """
        # Split by common sentence terminators
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Remove empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Group into chunks
        chunks = []
        for i in range(0, len(sentences), self.chunk_size):
            chunk = ' '.join(sentences[i:i + self.chunk_size])
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
        
        logger.info(f"Contract chunked: {len(sentences)} sentences → {len(chunks)} chunks")
        return chunks
    
    def filter_high_risk_chunks(
        self,
        contract_text: str,
        return_metadata: bool = True
    ) -> NLPFilterResult:
        """
        Main filtering function: Identify high-risk contract chunks using semantic similarity.
        
        Args:
            contract_text: Raw contract text to analyze
            return_metadata: Whether to return detailed match information
            
        Returns:
            NLPFilterResult containing high-risk chunks and match metadata
        """
        if not contract_text or len(contract_text.strip()) < 50:
            logger.warning("Contract text too short for NLP filtering")
            return NLPFilterResult(
                high_risk_chunks=[contract_text],
                matched_clauses=[],
                total_chunks=1,
                chunks_flagged=1,
                max_similarity=0.0,
                filter_ratio=0.0
            )
        
        # Step 1: Chunk the contract
        chunks = self._chunk_text(contract_text)
        
        if len(chunks) == 0:
            logger.warning("No valid chunks generated from contract")
            return NLPFilterResult(
                high_risk_chunks=[contract_text],
                matched_clauses=[],
                total_chunks=0,
                chunks_flagged=0,
                max_similarity=0.0,
                filter_ratio=0.0
            )
        
        # Step 2: Compute embeddings for contract chunks
        logger.info(f"Computing embeddings for {len(chunks)} contract chunks...")
        chunk_embeddings = self.model.encode(
            chunks,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        # Step 3: Compute cosine similarity matrix
        # Shape: (num_chunks, num_library_clauses)
        similarity_matrix = cosine_similarity(chunk_embeddings, self.clause_embeddings)
        
        # Step 4: Find matches above threshold
        matched_chunks = []
        chunk_matches = []
        
        for chunk_idx, chunk_similarities in enumerate(similarity_matrix):
            # Get best matching clause for this chunk
            max_similarity_idx = np.argmax(chunk_similarities)
            max_similarity = chunk_similarities[max_similarity_idx]
            
            if max_similarity >= self.similarity_threshold:
                matched_chunks.append(chunks[chunk_idx])
                
                if return_metadata:
                    chunk_matches.append(ChunkMatch(
                        chunk_text=chunks[chunk_idx],
                        matched_clause=self.clause_texts[max_similarity_idx],
                        similarity_score=float(max_similarity),
                        category=self.clause_metadata[max_similarity_idx]["category"],
                        severity=self.clause_metadata[max_similarity_idx]["severity"],
                        chunk_index=chunk_idx
                    ))
        
        # Step 5: Sort by similarity score (highest risk first) and cap at max_chunks
        if chunk_matches:
            chunk_matches.sort(key=lambda x: x.similarity_score, reverse=True)
            chunk_matches = chunk_matches[:self.max_chunks_to_send]
            matched_chunks = [m.chunk_text for m in chunk_matches]
        
        # Calculate metrics
        total_chunks = len(chunks)
        chunks_flagged = len(matched_chunks)
        max_sim = max([m.similarity_score for m in chunk_matches]) if chunk_matches else 0.0
        filter_ratio = 1.0 - (chunks_flagged / total_chunks) if total_chunks > 0 else 0.0
        
        logger.info(
            f"NLP Filtering Complete: {chunks_flagged}/{total_chunks} chunks flagged "
            f"(filtered out {filter_ratio*100:.1f}%) | Max similarity: {max_sim:.3f}"
        )
        
        # Fallback: If no matches found, return first N chunks to avoid silent failures
        if not matched_chunks:
            logger.warning(
                "No chunks matched threshold - sending first 10 chunks as fallback"
            )
            matched_chunks = chunks[:10]
        
        return NLPFilterResult(
            high_risk_chunks=matched_chunks,
            matched_clauses=chunk_matches,
            total_chunks=total_chunks,
            chunks_flagged=chunks_flagged,
            max_similarity=max_sim,
            filter_ratio=filter_ratio
        )
    
    def get_filtered_text_for_llm(self, contract_text: str) -> str:
        """
        Convenience method: Returns filtered text ready for LLM processing.
        Joins high-risk chunks with clear separators.
        """
        result = self.filter_high_risk_chunks(contract_text, return_metadata=False)
        
        # Join chunks with clear separators for LLM context
        filtered_text = "\n\n---CHUNK---\n\n".join(result.high_risk_chunks)
        
        logger.info(
            f"Filtered contract: {len(contract_text)} chars → "
            f"{len(filtered_text)} chars ({len(filtered_text)/len(contract_text)*100:.1f}%)"
        )
        
        return filtered_text
    
    def get_match_summary(self, result: NLPFilterResult) -> str:
        """Generate human-readable summary of matches"""
        if not result.matched_clauses:
            return "No high-risk clauses detected by NLP filter."
        
        category_counts = {}
        for match in result.matched_clauses:
            category_counts[match.category] = category_counts.get(match.category, 0) + 1
        
        summary_lines = [
            f"NLP Filter Results: {result.chunks_flagged}/{result.total_chunks} chunks flagged",
            f"Filter Efficiency: {result.filter_ratio*100:.1f}% of text filtered out",
            f"Max Similarity Score: {result.max_similarity:.3f}",
            "\nDetected Categories:"
        ]
        
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            summary_lines.append(f"  • {category}: {count} match(es)")
        
        return "\n".join(summary_lines)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE (Lazy-loaded for efficiency)
# ══════════════════════════════════════════════════════════════════════════════

_ENGINE_INSTANCE: Optional[NLPVectorizationEngine] = None

def get_nlp_engine(
    model_name: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.65,
    force_reload: bool = False
) -> NLPVectorizationEngine:
    """
    Get singleton NLP engine instance (lazy-loaded).
    Model is loaded once and reused across requests for efficiency.
    
    Args:
        model_name: SentenceTransformer model to use
        similarity_threshold: Cosine similarity threshold for matches
        force_reload: Force reload of the model (use sparingly)
    """
    global _ENGINE_INSTANCE
    
    if _ENGINE_INSTANCE is None or force_reload:
        logger.info("Initializing NLP engine singleton...")
        _ENGINE_INSTANCE = NLPVectorizationEngine(
            model_name=model_name,
            similarity_threshold=similarity_threshold
        )
    
    return _ENGINE_INSTANCE


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT LIBRARY DATA (For external use)
# ══════════════════════════════════════════════════════════════════════════════

def export_clause_library_json(filepath: str = "predatory_clauses.json") -> None:
    """Export the clause library to JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(PREDATORY_CLAUSE_LIBRARY, f, indent=2)
    logger.info(f"Clause library exported to {filepath}")


def get_clause_library_stats() -> Dict[str, int]:
    """Get statistics about the clause library"""
    category_counts = {}
    severity_counts = {}
    
    for clause in PREDATORY_CLAUSE_LIBRARY:
        cat = clause["category"]
        sev = clause["severity"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    return {
        "total_clauses": len(PREDATORY_CLAUSE_LIBRARY),
        "categories": category_counts,
        "severities": severity_counts
    }
