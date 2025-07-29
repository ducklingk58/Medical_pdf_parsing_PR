"""
Medical PDF 파싱 프로젝트 (Medical_pdf_parsing_PR)

Unstructured 라이브러리를 활용한 대량 의료 PDF 고급 파싱 시스템

이 프로젝트는 500개의 의료 제품 관련 PDF 파일을 Unstructured를 활용하여 
고급 파싱 및 후처리하는 시스템입니다.

주요 기능:
- Unstructured 기반 고급 파싱
- LayoutParser + PaddleOCR 고급 테이블/이미지 파싱
- 의미론적 문장 연결
- 구조화된 표 처리
- RAG 친화적 청킹
- 병렬 처리 및 모니터링
- Streamlit 대시보드
"""

__version__ = "2.0.0"
__author__ = "Medical_pdf_parsing_PR Team"
__description__ = "Unstructured + LayoutParser + PaddleOCR 기반 의료 PDF 고급 파싱 시스템"

from .main_processor import EnhancedPDFProcessor
from .batch_processor import BatchPDFProcessor
from .utils.pdf_processor import PDFProcessor
from .config.settings import Settings

__all__ = [
    "EnhancedPDFProcessor",
    "BatchPDFProcessor",
    "PDFProcessor", 
    "Settings"
] 