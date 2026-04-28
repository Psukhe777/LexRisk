"""
ocr_processor.py — OCR Fallback Engine for Image-Based PDFs
Purpose: Extract text from scanned PDFs when pdfplumber returns insufficient text
Features:
- PyTesseract OCR with image preprocessing
- Automatic fallback detection (< 50 chars threshold)
- Multi-page PDF support with progress tracking
- Image quality enhancement (contrast, deskew, denoise)
- Configurable OCR settings (language, PSM mode)
"""

import logging
import io
import os
from typing import Optional, Tuple, List
from dataclasses import dataclass
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

try:
    import pytesseract
    from pdf2image import convert_from_path, convert_from_bytes
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    pytesseract = None
    convert_from_path = None
    convert_from_bytes = None

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Tesseract OCR configuration
TESSERACT_CONFIG = r'--oem 3 --psm 6'  # PSM 6: Assume uniform block of text
DEFAULT_LANGUAGE = 'eng'  # Language code (eng, spa, fra, deu, etc.)
MIN_TEXT_THRESHOLD = 50  # Minimum chars to consider pdfplumber successful
MAX_OCR_PAGES = 100  # Hard cap on OCR pages to prevent runaway costs

# Image preprocessing settings
ENABLE_PREPROCESSING = True
CONTRAST_ENHANCEMENT_FACTOR = 1.5
SHARPNESS_ENHANCEMENT_FACTOR = 2.0
DENOISE_RADIUS = 1


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OCRResult:
    """Result from OCR processing"""
    text: str
    page_count: int
    total_chars: int
    ocr_confidence: float  # Average confidence score (0-100)
    preprocessing_applied: bool
    processing_time_ms: int
    fallback_triggered: bool  # Whether this was a fallback from pdfplumber


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Enhance image quality for better OCR accuracy.
    
    Steps:
    1. Convert to grayscale
    2. Increase contrast
    3. Sharpen edges
    4. Denoise
    5. Binarize (optional, for very poor quality scans)
    """
    if not ENABLE_PREPROCESSING:
        return image
    
    try:
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(CONTRAST_ENHANCEMENT_FACTOR)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(SHARPNESS_ENHANCEMENT_FACTOR)
        
        # Denoise
        image = image.filter(ImageFilter.MedianFilter(size=DENOISE_RADIUS))
        
        # Optional: Binarization (Otsu's method)
        # Uncomment for very low-quality scans
        # image_array = np.array(image)
        # threshold = threshold_otsu(image_array)
        # binary = image_array > threshold
        # image = Image.fromarray((binary * 255).astype(np.uint8))
        
        logger.debug("Image preprocessing complete")
        return image
        
    except Exception as e:
        logger.warning(f"Image preprocessing failed: {e}, using original")
        return image


# ══════════════════════════════════════════════════════════════════════════════
# OCR ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class OCRProcessor:
    """
    OCR processing engine with automatic fallback detection.
    """
    
    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
        config: str = TESSERACT_CONFIG,
        enable_preprocessing: bool = ENABLE_PREPROCESSING
    ):
        """
        Initialize OCR processor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (auto-detect if None)
            language: Tesseract language code
            config: Tesseract configuration string
            enable_preprocessing: Enable image preprocessing
        """
        if not PYTESSERACT_AVAILABLE:
            raise ImportError(
                "pytesseract and pdf2image are required for OCR. "
                "Install with: pip install pytesseract pdf2image"
            )
        
        # Set tesseract command path if provided
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self.language = language
        self.config = config
        self.enable_preprocessing = enable_preprocessing
        
        # Verify tesseract is installed
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"✅ Tesseract OCR initialized (version {version})")
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            raise RuntimeError(
                "Tesseract OCR not installed. "
                "Install from: https://github.com/tesseract-ocr/tesseract"
            )
    
    def should_use_ocr(self, pdfplumber_text: str) -> bool:
        """
        Determine if OCR fallback should be triggered.
        
        Args:
            pdfplumber_text: Text extracted by pdfplumber
            
        Returns:
            True if OCR should be used, False otherwise
        """
        if not pdfplumber_text:
            logger.info("OCR triggered: pdfplumber returned empty text")
            return True
        
        text_length = len(pdfplumber_text.strip())
        
        if text_length < MIN_TEXT_THRESHOLD:
            logger.info(
                f"OCR triggered: pdfplumber returned only {text_length} chars "
                f"(threshold: {MIN_TEXT_THRESHOLD})"
            )
            return True
        
        logger.info(f"OCR not needed: pdfplumber extracted {text_length} chars")
        return False
    
    def extract_text_from_pdf(
        self,
        pdf_file,
        max_pages: Optional[int] = None
    ) -> OCRResult:
        """
        Extract text from PDF using OCR.
        
        Args:
            pdf_file: File-like object or path to PDF
            max_pages: Maximum pages to process (None = all)
            
        Returns:
            OCRResult with extracted text and metadata
        """
        import time
        start_time = time.time()
        
        # Convert PDF to images
        try:
            if hasattr(pdf_file, 'read'):
                # File-like object
                pdf_bytes = pdf_file.read()
                images = convert_from_bytes(pdf_bytes)
                # Reset file pointer for potential re-use
                pdf_file.seek(0)
            else:
                # File path
                images = convert_from_path(pdf_file)
            
            total_pages = len(images)
            logger.info(f"PDF converted to {total_pages} image(s)")
            
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise ValueError(f"Failed to convert PDF to images: {e}")
        
        # Apply page limit
        if max_pages:
            pages_to_process = min(total_pages, max_pages, MAX_OCR_PAGES)
        else:
            pages_to_process = min(total_pages, MAX_OCR_PAGES)
        
        if pages_to_process < total_pages:
            logger.warning(
                f"Processing only {pages_to_process}/{total_pages} pages "
                f"(limit: {MAX_OCR_PAGES})"
            )
        
        # Process each page
        page_texts = []
        confidence_scores = []
        
        for i, image in enumerate(images[:pages_to_process]):
            logger.debug(f"Processing page {i+1}/{pages_to_process}...")
            
            # Preprocess image
            if self.enable_preprocessing:
                image = preprocess_image(image)
            
            # Run OCR
            try:
                # Get detailed OCR data (includes confidence scores)
                ocr_data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config=self.config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Extract text and confidence
                page_text = pytesseract.image_to_string(
                    image,
                    lang=self.language,
                    config=self.config
                )
                
                # Calculate average confidence for this page
                confidences = [
                    float(conf) for conf in ocr_data['conf']
                    if conf != '-1'  # -1 means no confidence score
                ]
                page_confidence = np.mean(confidences) if confidences else 0.0
                
                page_texts.append(page_text)
                confidence_scores.append(page_confidence)
                
                logger.debug(
                    f"Page {i+1}: {len(page_text)} chars, "
                    f"confidence: {page_confidence:.1f}%"
                )
                
            except Exception as e:
                logger.error(f"OCR failed on page {i+1}: {e}")
                page_texts.append("")
                confidence_scores.append(0.0)
        
        # Combine all pages
        full_text = "\n\n".join(page_texts)
        total_chars = len(full_text)
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"✅ OCR complete: {total_chars:,} chars from {pages_to_process} pages | "
            f"Confidence: {avg_confidence:.1f}% | Time: {processing_time_ms}ms"
        )
        
        return OCRResult(
            text=full_text,
            page_count=pages_to_process,
            total_chars=total_chars,
            ocr_confidence=avg_confidence,
            preprocessing_applied=self.enable_preprocessing,
            processing_time_ms=processing_time_ms,
            fallback_triggered=True
        )
    
    def extract_text_with_fallback(
        self,
        pdf_file,
        pdfplumber_text: str,
        max_pages: Optional[int] = None
    ) -> Tuple[str, bool, Optional[OCRResult]]:
        """
        Smart extraction: Use pdfplumber text if sufficient, otherwise OCR.
        
        Args:
            pdf_file: File-like object or path to PDF
            pdfplumber_text: Text already extracted by pdfplumber
            max_pages: Maximum pages to OCR
            
        Returns:
            Tuple of (final_text, ocr_was_used, ocr_result_if_used)
        """
        if not self.should_use_ocr(pdfplumber_text):
            # pdfplumber text is sufficient
            return pdfplumber_text, False, None
        
        # Trigger OCR fallback
        logger.info("🔍 Triggering OCR fallback...")
        ocr_result = self.extract_text_from_pdf(pdf_file, max_pages)
        
        return ocr_result.text, True, ocr_result


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_OCR_PROCESSOR_INSTANCE: Optional[OCRProcessor] = None

def get_ocr_processor(
    tesseract_cmd: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    force_reload: bool = False
) -> OCRProcessor:
    """
    Get singleton OCR processor instance (lazy-loaded).
    
    Args:
        tesseract_cmd: Path to tesseract executable
        language: Tesseract language code
        force_reload: Force reload of processor
        
    Returns:
        OCRProcessor instance
    """
    global _OCR_PROCESSOR_INSTANCE
    
    if _OCR_PROCESSOR_INSTANCE is None or force_reload:
        logger.info("Initializing OCR processor singleton...")
        _OCR_PROCESSOR_INSTANCE = OCRProcessor(
            tesseract_cmd=tesseract_cmd,
            language=language
        )
    
    return _OCR_PROCESSOR_INSTANCE


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def is_ocr_available() -> bool:
    """Check if OCR dependencies are installed"""
    if not PYTESSERACT_AVAILABLE:
        return False
    
    try:
        # Try to get tesseract version
        pytesseract.get_tesseract_version()
        return True
    except:
        return False


def get_ocr_status_message() -> str:
    """Get human-readable OCR availability status"""
    if not PYTESSERACT_AVAILABLE:
        return (
            "❌ OCR unavailable: pytesseract or pdf2image not installed. "
            "Install with: pip install pytesseract pdf2image"
        )
    
    try:
        version = pytesseract.get_tesseract_version()
        return f"✅ OCR available (Tesseract {version})"
    except:
        return (
            "❌ OCR unavailable: Tesseract binary not found. "
            "Install from: https://github.com/tesseract-ocr/tesseract"
        )


def estimate_ocr_time(page_count: int) -> int:
    """
    Estimate OCR processing time in seconds.
    
    Based on empirical testing:
    - ~2-3 seconds per page with preprocessing
    - ~1-2 seconds per page without preprocessing
    """
    seconds_per_page = 2.5 if ENABLE_PREPROCESSING else 1.5
    return int(page_count * seconds_per
