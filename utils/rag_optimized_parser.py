"""
RAG 최적화 PDF 파싱 시스템
목표 스키마에 맞춘 구조화된 JSON 출력 생성
"""

import os
import re
import json
import uuid
import base64
import fitz  # PyMuPDF
import pandas as pd
import numpy as np
import cv2
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import logging
from PIL import Image
import io
import tempfile

# PaddleOCR imports
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("Warning: PaddleOCR not available. OCR features will be disabled.")

# Unstructured imports
try:
    from unstructured.partition.auto import partition
    from unstructured.documents.elements import Table, Title, NarrativeText, Image as UnstructuredImage
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    print("Warning: Unstructured not available. Text extraction will be limited.")

# 기존 설정 import
try:
    from config.settings import Settings
except ImportError:
    # 기본 설정 클래스
    class Settings:
        SIMILARITY_THRESHOLD = 0.8
        SENTENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
        REMOVE_PAGE_NUMBERS = True
        REMOVE_HEADERS_FOOTERS = True
        INCLUDE_IMAGE_METADATA = True
        PDF_EXTRACT_TABLES = True
        PDF_EXTRACT_IMAGES = True
        
        @staticmethod
        def create_directories():
            pass

class RAGOptimizedParser:
    """RAG 최적화 JSON 스키마에 맞춘 PDF 파싱기"""
    
    def __init__(self, use_gpu: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # PaddleOCR 초기화 (가능한 경우)
        self.ocr_system = self._init_paddle_ocr() if PADDLEOCR_AVAILABLE else None
        
        # 임시 디렉토리 생성
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 문서 메타데이터
        self.document_title = ""
        self.document_id = str(uuid.uuid4())
        self.source_pdf_filename = ""
        
        self.logger.info(f"RAG 최적화 파싱기 초기화 완료 (GPU: {use_gpu})")
    
    def _init_paddle_ocr(self) -> Optional[PaddleOCR]:
        """PaddleOCR 시스템 초기화"""
        if not PADDLEOCR_AVAILABLE:
            return None
            
        try:
            # 가장 기본적인 초기화
            ocr_system = PaddleOCR()  # 모든 매개변수 제거
            self.logger.info("PaddleOCR 시스템 초기화 성공 (기본 설정)")
            return ocr_system
        except Exception as e:
            self.logger.error(f"PaddleOCR 초기화 실패: {str(e)}")
            return None
    
    def extract_document_metadata(self, pdf_path: str) -> Dict[str, str]:
        """문서 레벨 메타데이터 추출"""
        try:
            self.source_pdf_filename = Path(pdf_path).name
            
            # PDF 문서 열기
            doc = fitz.open(pdf_path)
            
            # 첫 페이지에서 제목 추출 시도
            first_page = doc.load_page(0)
            text_blocks = first_page.get_text("dict")["blocks"]
            
            # 제목 후보들 찾기 (큰 폰트, 상단 위치)
            title_candidates = []
            for block in text_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span["size"]
                            y_pos = span["bbox"][1]  # y 좌표
                            text = span["text"].strip()
                            
                            if font_size > 14 and y_pos < 200 and text:  # 큰 폰트, 상단 위치
                                title_candidates.append((text, font_size, y_pos))
            
            # 가장 큰 폰트와 상단에 위치한 텍스트를 제목으로 선택
            if title_candidates:
                title_candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
                self.document_title = title_candidates[0][0]
            else:
                # 기본값으로 파일명 사용
                self.document_title = Path(pdf_path).stem
            
            doc.close()
            
            return {
                "document_title": self.document_title,
                "document_id": self.document_id,
                "created_at": datetime.now().isoformat(),
                "source_pdf_filename": self.source_pdf_filename
            }
            
        except Exception as e:
            self.logger.error(f"문서 메타데이터 추출 오류: {str(e)}")
            return {
                "document_title": Path(pdf_path).stem,
                "document_id": self.document_id,
                "created_at": datetime.now().isoformat(),
                "source_pdf_filename": self.source_pdf_filename
            }
    
    def pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[Tuple[int, np.ndarray, Dict]]:
        """PDF를 고해상도 이미지로 변환하고 페이지 메타데이터 포함"""
        try:
            self.logger.info(f"PDF를 이미지로 변환 중: {pdf_path}")
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 고해상도 이미지로 렌더링
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Image로 변환
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # OpenCV 형식으로 변환
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                
                # 페이지 메타데이터
                page_metadata = {
                    "page_number": page_num + 1,
                    "width": pix.width,
                    "height": pix.height,
                    "rotation": page.rotation
                }
                
                images.append((page_num, cv_image, page_metadata))
                pix = None
            
            doc.close()
            self.logger.info(f"총 {len(images)}페이지 이미지 변환 완료")
            return images
            
        except Exception as e:
            self.logger.error(f"PDF 이미지 변환 오류: {str(e)}")
            return []  # 빈 리스트 반환으로 변경
    
    def extract_text_chunks(self, pdf_path: str) -> List[Dict[str, Any]]:
        """텍스트 청크 추출 및 상세 메타데이터 생성"""
        try:
            self.logger.info("텍스트 청크 추출 시작")
            
            text_chunks = []
            doc = fitz.open(pdf_path)
            
            if UNSTRUCTURED_AVAILABLE:
                # Unstructured로 기본 파싱
                elements = partition(
                    filename=pdf_path,
                    include_image_metadata=True,
                    extract_tables=False,  # 표는 별도로 처리
                    pdf_extract_images=False,  # 이미지는 별도로 처리
                    strategy="fast"
                )
                
                for i, element in enumerate(elements):
                    if isinstance(element, (NarrativeText, Title)):
                        chunk_data = self._create_text_chunk(element, doc, i)
                        if chunk_data:
                            # 텍스트 청크임을 명시
                            chunk_data["type"] = "text"
                            chunk_data["subtype"] = "narrative" if isinstance(element, NarrativeText) else "title"
                            text_chunks.append(chunk_data)
            else:
                # PyMuPDF만 사용한 텍스트 추출
                text_chunks = self._extract_text_with_pymupdf(doc)
                # 기본 타입 설정 (이미 _extract_text_with_pymupdf에서 설정됨)
                pass
            
            doc.close()
            self.logger.info(f"총 {len(text_chunks)}개 텍스트 청크 추출 완료")
            return text_chunks
            
        except Exception as e:
            self.logger.error(f"텍스트 청크 추출 오류: {str(e)}")
            return []
    
    def _create_text_chunk(self, element, doc, index: int) -> Optional[Dict[str, Any]]:
        """Unstructured 요소로부터 텍스트 청크 생성"""
        try:
            chunk_id = str(uuid.uuid4())
            
            # 기본 정보
            content = element.text.strip()
            if not content:
                return None
            
            # 카테고리 결정
            category = self._determine_category(element)
            
            # 페이지 번호 추출
            page_numbers = self._extract_page_numbers(element, doc)
            
            # 좌표 추출 (가능한 경우)
            coordinates = self._extract_coordinates(element, doc)
            
            # 섹션 제목 추출
            section_title = self._extract_section_title(content, index)
            
            # 표/그림 관련성 확인
            is_table_related, is_figure_related = self._check_element_relation(content)
            
            chunk_data = {
                "chunk_id": chunk_id,
                "content": content,
                "type": "text",  # 텍스트 청크임을 명시
                "subtype": "narrative" if isinstance(element, NarrativeText) else "title",
                "section_title": section_title,
                "category": category,
                "page_numbers": page_numbers,
                "coordinates": coordinates,
                "is_table_related": is_table_related,
                "is_figure_related": is_figure_related,
                "referenced_element_id": None,  # 나중에 연결
                "extraction_tool": "Unstructured",
                "confidence_score": 0.9  # 기본값
            }
            
            return chunk_data
            
        except Exception as e:
            self.logger.error(f"텍스트 청크 생성 오류: {str(e)}")
            return None
    
    def _extract_text_with_pymupdf(self, doc) -> List[Dict[str, Any]]:
        """PyMuPDF만 사용한 텍스트 추출"""
        text_chunks = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_blocks = page.get_text("dict")["blocks"]
            
            for block in text_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text and len(text) > 10:  # 의미있는 텍스트만
                                chunk_id = str(uuid.uuid4())
                                
                                # 폰트 크기로 카테고리 결정
                                font_size = span["size"]
                                if font_size > 16:
                                    category = "Title"
                                elif font_size > 12:
                                    category = "Subtitle"
                                else:
                                    category = "NarrativeText"
                                
                                chunk_data = {
                                    "chunk_id": chunk_id,
                                    "content": text,
                                    "type": "text",  # 텍스트 청크임을 명시
                                    "subtype": "pymupdf",
                                    "section_title": "",
                                    "category": category,
                                    "page_numbers": [page_num + 1],
                                    "coordinates": list(span["bbox"]),
                                    "is_table_related": "표" in text or "table" in text.lower(),
                                    "is_figure_related": "그림" in text or "figure" in text.lower(),
                                    "referenced_element_id": None,
                                    "extraction_tool": "PyMuPDF",
                                    "confidence_score": 0.8
                                }
                                
                                text_chunks.append(chunk_data)
        
        return text_chunks
    
    def _determine_category(self, element) -> str:
        """요소의 카테고리 결정"""
        if isinstance(element, Title):
            return "Title"
        elif isinstance(element, NarrativeText):
            text = element.text.lower()
            if any(keyword in text for keyword in ["표", "table", "figure", "그림"]):
                return "Caption"
            elif any(keyword in text for keyword in ["•", "-", "1.", "2.", "3."]):
                return "ListItem"
            else:
                return "NarrativeText"
        else:
            return "Text"
    
    def _extract_page_numbers(self, element, doc) -> List[int]:
        """페이지 번호 추출"""
        try:
            # Unstructured의 메타데이터에서 페이지 정보 추출
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'page_number'):
                return [element.metadata.page_number]
            
            # 기본값
            return [1]
        except:
            return [1]
    
    def _extract_coordinates(self, element, doc) -> List[float]:
        """좌표 추출 (기본값 반환)"""
        # 실제 구현에서는 PyMuPDF를 사용하여 정확한 좌표 추출
        return [0.0, 0.0, 100.0, 100.0]  # 기본값
    
    def _extract_section_title(self, content: str, index: int) -> str:
        """섹션 제목 추출"""
        # 간단한 패턴 매칭으로 섹션 제목 추출
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # 숫자로 시작하는 제목 패턴
            if re.match(r'^\d+\.', line):
                return line
            # 대문자로 시작하는 짧은 제목
            elif len(line) < 50 and line.isupper():
                return line
        
        return ""
    
    def _check_element_relation(self, content: str) -> Tuple[bool, bool]:
        """텍스트가 표나 그림과 관련있는지 확인"""
        content_lower = content.lower()
        is_table_related = any(keyword in content_lower for keyword in ["표", "table", "테이블"])
        is_figure_related = any(keyword in content_lower for keyword in ["그림", "figure", "도", "차트"])
        return is_table_related, is_figure_related
    
    def extract_tables(self, pdf_path: str) -> List[Dict[str, Any]]:
        """표 데이터 추출 및 구조화 - Microsoft Table Transformer 전용"""
        try:
            self.logger.info("표 추출 시작 (Microsoft Table Transformer)")
            
            tables = []
            
            # 1차: Table Transformer 시도 (주 엔진)
            try:
                from utils.table_transformer_detector import TableTransformerDetector, TRANSFORMER_AVAILABLE
                
                if TRANSFORMER_AVAILABLE:
                    self.logger.info("🚀 Microsoft Table Transformer 표 감지 시작...")
                    detector = TableTransformerDetector()
                    tt_result = detector.detect_tables_in_pdf(pdf_path, confidence_threshold=0.5)  # 낮은 임계값으로 더 많이 감지
                    
                    if tt_result["success"] and tt_result["tables"]:
                        self.logger.info(f"✅ Table Transformer: {len(tt_result['tables'])}개 표 감지")
                        
                        # 내용까지 추출된 완전한 결과 사용
                        enhanced_result = detector.process_pdf_with_table_transformer(pdf_path, confidence_threshold=0.5)
                        
                        if enhanced_result["success"] and enhanced_result["tables"]:
                            for table in enhanced_result["tables"]:
                                rag_table = {
                                    "table_id": table.get('table_id', str(uuid.uuid4())),
                                    "caption": f"표 {table.get('page_number', 1)} (Table Transformer)",
                                    "page_number": table.get('page_number', 1),
                                    "coordinates": table.get('coordinates', []),
                                    "structure": {"rows": 0, "columns": 0},  # 구조는 OCR 결과로 업데이트
                                    "table_data": table.get('table_data', []),
                                    "extracted_text": table.get('extracted_text', ''),
                                    "extraction_tool": "Microsoft_Table_Transformer",
                                    "confidence_score": table.get('confidence_score', 0.0),
                                    "bbox": table.get('bbox', {}),
                                    "cell_texts": table.get('cell_texts', []),
                                    "ocr_method": table.get('ocr_method', 'PaddleOCR'),
                                    "avg_confidence": table.get('avg_confidence', 0.0)
                                }
                                tables.append(rag_table)
                        
                        self.logger.info(f"Table Transformer로 {len(tables)}개 표 감지 및 내용 추출 완료")
                        
                    else:
                        self.logger.info("Table Transformer에서 표를 감지하지 못함")
                else:
                    self.logger.warning("Table Transformer 라이브러리가 설치되지 않았습니다.")
                    self.logger.info("설치 명령: pip install transformers torch torchvision")
                    
            except Exception as e:
                self.logger.error(f"Table Transformer 실패: {str(e)}")
            
            # 2차: 패턴 기반 가상 표 생성 (보조 엔진)
            try:
                self.logger.info("🔄 구조화된 텍스트 패턴 기반 가상 표 생성...")
                pattern_tables = self._extract_structured_text_as_tables(pdf_path)
                
                if pattern_tables:
                    self.logger.info(f"패턴 기반으로 {len(pattern_tables)}개 가상 표 생성")
                    tables.extend(pattern_tables)
                    
            except Exception as e:
                self.logger.warning(f"패턴 기반 표 생성 실패: {str(e)}")
            
            # 최종 결과
            if tables:
                self.logger.info(f"총 {len(tables)}개 표 추출 완료 (Table Transformer + 패턴 기반)")
            else:
                self.logger.warning("어떤 방법으로도 표를 감지하지 못했습니다.")
                
            return tables
            
        except Exception as e:
            self.logger.error(f"표 추출 실패: {str(e)}")
            return []
    
    def _extract_table_text(self, table_data: List) -> str:
        """테이블 데이터에서 텍스트 추출"""
        if not table_data:
            return ""
        
        text_parts = []
        for row in table_data:
            if isinstance(row, list):
                for cell in row:
                    if cell and str(cell).strip():
                        text_parts.append(str(cell).strip())
            elif isinstance(row, str) and row.strip():
                text_parts.append(row.strip())
        
        return " ".join(text_parts)
    
    def _extract_tables_fallback(self, pdf_path: str) -> List[Dict[str, Any]]:
        """기본 테이블 추출 방법 (폴백)"""
        try:
            self.logger.info("기본 테이블 추출 방법 사용")
            
            tables = []
            doc = fitz.open(pdf_path)
            
            # PyMuPDF를 사용한 간단한 표 감지
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 표 감지를 위한 간단한 방법 (텍스트 블록 분석)
                text_blocks = page.get_text("dict")["blocks"]
                
                # 표 후보 찾기 (정렬된 텍스트 블록들)
                table_candidates = self._find_table_candidates(text_blocks, page_num)
                
                for i, candidate in enumerate(table_candidates):
                    table_id = str(uuid.uuid4())
                    
                    # 간단한 표 구조 생성
                    structure = self._create_simple_table_structure(candidate)
                    
                    table_data = {
                        "table_id": table_id,
                        "caption": f"표 {page_num + 1}-{i + 1}",
                        "page_number": page_num + 1,
                        "coordinates": [0.0, 0.0, 100.0, 100.0],  # 기본값
                        "structure": structure,
                        "extracted_text": " ".join([cell for row in structure for cell in row if cell]),
                        "extraction_tool": "PyMuPDF_Simple",
                        "confidence_score": 0.7,
                        "file_path": None
                    }
                    
                    tables.append(table_data)
            
            doc.close()
            return tables
            
        except Exception as e:
            self.logger.error(f"기본 표 추출 오류: {str(e)}")
            return []
    
    def _find_table_candidates(self, text_blocks, page_num: int) -> List[List]:
        """텍스트 블록에서 표 후보 찾기"""
        candidates = []
        
        # 간단한 표 감지 로직
        # 여러 줄에 걸쳐 정렬된 텍스트 블록들을 표로 간주
        lines = []
        for block in text_blocks:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = " ".join([span["text"] for span in line["spans"]])
                    if line_text.strip():
                        lines.append(line_text.strip())
        
        # 연속된 줄들을 표 후보로 간주
        if len(lines) > 2:
            candidates.append(lines)
        
        return candidates
    
    def _create_simple_table_structure(self, lines: List[str]) -> List[List[str]]:
        """간단한 표 구조 생성"""
        structure = []
        
        for line in lines:
            # 탭이나 여러 공백으로 구분된 셀들
            cells = re.split(r'\t+|\s{2,}', line)
            cells = [cell.strip() for cell in cells if cell.strip()]
            if cells:
                structure.append(cells)
        
        return structure
    
    def extract_figures(self, pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
        """그림 데이터 추출 (간단한 버전)"""
        try:
            self.logger.info("그림 추출 시작")
            
            figures = []
            doc = fitz.open(pdf_path)
            
            # 이미지 저장 디렉토리
            images_dir = Path(output_dir) / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 페이지에서 이미지 추출
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    figure_id = str(uuid.uuid4())
                    
                    try:
                        # 이미지 데이터 추출
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        # 이미지 파일 저장
                        image_filename = f"figure_{figure_id[:8]}.png"
                        image_path = images_dir / image_filename
                        pix.save(str(image_path))
                        
                        # Base64 인코딩 (작은 이미지의 경우)
                        image_base64 = None
                        if pix.size < 1000000:  # 1MB 미만
                            img_data = pix.tobytes("png")
                            image_base64 = base64.b64encode(img_data).decode('utf-8')
                        
                        figure_data = {
                            "figure_id": figure_id,
                            "caption": f"그림 {page_num + 1}-{img_index + 1}",
                            "page_number": page_num + 1,
                            "coordinates": [0.0, 0.0, 100.0, 100.0],  # 기본값
                            "image_base64": image_base64,
                            "image_path": str(image_path.relative_to(output_dir)),
                            "extracted_text": "",
                            "extraction_tool": "PyMuPDF",
                            "confidence_score": 0.8
                        }
                        
                        figures.append(figure_data)
                        pix = None
                        
                    except Exception as e:
                        self.logger.warning(f"이미지 추출 실패: {str(e)}")
                        continue
            
            doc.close()
            self.logger.info(f"총 {len(figures)}개 그림 추출 완료")
            return figures
            
        except Exception as e:
            self.logger.error(f"그림 추출 오류: {str(e)}")
            return []
    
    def link_elements(self, text_chunks: List[Dict], tables: List[Dict], figures: List[Dict]) -> List[Dict]:
        """텍스트 청크와 표/그림 간의 연결 고리 생성"""
        try:
            self.logger.info("요소 간 연결 고리 생성 시작")
            
            # 표/그림 ID 매핑 생성
            table_captions = {table["caption"]: table["table_id"] for table in tables if table["caption"]}
            figure_captions = {figure["caption"]: figure["figure_id"] for figure in figures if figure["caption"]}
            
            # 텍스트 청크 업데이트
            for chunk in text_chunks:
                content = chunk["content"].lower()
                
                # 표 관련성 확인 및 연결
                if chunk["is_table_related"]:
                    for caption, table_id in table_captions.items():
                        if caption.lower() in content or any(word in content for word in caption.lower().split()):
                            chunk["referenced_element_id"] = table_id
                            break
                
                # 그림 관련성 확인 및 연결
                if chunk["is_figure_related"]:
                    for caption, figure_id in figure_captions.items():
                        if caption.lower() in content or any(word in content for word in caption.lower().split()):
                            chunk["referenced_element_id"] = figure_id
                            break
            
            self.logger.info("요소 간 연결 고리 생성 완료")
            return text_chunks
            
        except Exception as e:
            self.logger.error(f"요소 연결 오류: {str(e)}")
            return text_chunks
    
    def create_unified_chunks(self, text_chunks: List[Dict[str, Any]], tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """텍스트와 표 청크를 통합하여 단일 청크 리스트 생성"""
        try:
            from utils.table_to_text_converter import TableToTextConverter
            
            self.logger.info("통합 청크 생성 시작")
            
            converter = TableToTextConverter()
            unified_chunks = []
            chunk_counter = 0
            
            # 1. 기존 텍스트 청크 추가 (타입 명시)
            for text_chunk in text_chunks:
                text_chunk["chunk_index"] = chunk_counter
                unified_chunks.append(text_chunk)
                chunk_counter += 1
            
            # 2. 표 청크 생성 및 추가
            for table in tables:
                table_chunks = converter.create_table_chunks(table, f"chunk_{chunk_counter:06d}")
                
                for table_chunk in table_chunks:
                    table_chunk["chunk_index"] = chunk_counter
                    unified_chunks.append(table_chunk)
                    chunk_counter += 1
            
            # 3. 페이지 순서대로 정렬
            unified_chunks.sort(key=lambda x: (x.get('page_number', 1), x.get('chunk_index', 0)))
            
            # 4. 최종 ID 재할당
            for i, chunk in enumerate(unified_chunks):
                chunk["id"] = f"chunk_{i:06d}"
                chunk["chunk_index"] = i
            
            self.logger.info(f"통합 청크 생성 완료: 텍스트 {len(text_chunks)}개 + 표 {chunk_counter - len(text_chunks)}개 = 총 {len(unified_chunks)}개")
            
            return unified_chunks
            
        except Exception as e:
            self.logger.error(f"통합 청크 생성 실패: {str(e)}")
            # 기본적으로 텍스트 청크만 반환
            return text_chunks

    def process_pdf(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """PDF 처리 메인 함수 - 향상된 표/텍스트 구분 처리"""
        try:
            self.logger.info(f"RAG 최적화 PDF 처리 시작: {pdf_path}")
            
            # 출력 디렉토리 생성
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 1. 문서 메타데이터 추출
            document_metadata = self.extract_document_metadata(pdf_path)
            
            # 2. 텍스트 청크 추출
            text_chunks = self.extract_text_chunks(pdf_path)
            
            # 3. 표 추출
            tables = self.extract_tables(pdf_path)
            
            # 4. 그림 추출
            figures = self.extract_figures(pdf_path, output_dir)
            
            # 5. 통합 청크 생성 (텍스트 + 표 청크)
            unified_chunks = self.create_unified_chunks(text_chunks, tables)
            
            # 6. 요소 간 연결 고리 생성
            enhanced_chunks = self.link_elements(unified_chunks, tables, figures)
            
            # 7. 청크 통계 계산
            chunk_stats = self._calculate_chunk_statistics(enhanced_chunks)
            
            # 8. 최종 JSON 구조 생성
            result = {
                **document_metadata,
                "text_chunks": enhanced_chunks,
                "tables": tables,
                "figures": figures,
                "chunk_statistics": chunk_stats
            }
            
            # 9. JSON 파일 저장
            output_filename = f"{Path(pdf_path).stem}_parsed.json"
            output_file = output_path / output_filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"RAG 최적화 파싱 완료: {output_file}")
            
            return {
                "success": True,
                "output_file": str(output_file),
                "text_chunks_count": len([c for c in enhanced_chunks if c.get('type') == 'text']),
                "table_chunks_count": len([c for c in enhanced_chunks if c.get('type') == 'table']),
                "total_chunks_count": len(enhanced_chunks),
                "tables_count": len(tables),
                "figures_count": len(figures),
                "chunk_statistics": chunk_stats
            }
            
        except Exception as e:
            self.logger.error(f"PDF 처리 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_structured_text_as_tables(self, pdf_path: str) -> List[Dict[str, Any]]:
        """구조화된 텍스트 패턴을 표로 변환"""
        try:
            self.logger.info("구조화된 텍스트 패턴 기반 가상 표 생성 시작")
            
            # 텍스트 추출
            text_chunks = self.extract_text_chunks(pdf_path)
            
            virtual_tables = []
            
            # 구조화된 패턴 찾기
            structured_patterns = ['①', '②', '③', '④', '⑤', '가)', '나)', '다)', '라)', '마)']
            current_table_items = []
            current_page = 1
            table_counter = 1
            
            for chunk in text_chunks:
                text = chunk.get('text', '')
                page_num = chunk.get('page_number', current_page)
                
                # 구조화된 항목인지 확인
                has_pattern = any(pattern in text for pattern in structured_patterns)
                
                if has_pattern:
                    # 여러 패턴이 한 텍스트에 있는 경우 분리
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if any(pattern in line for pattern in structured_patterns):
                            current_table_items.append({
                                'text': line,
                                'page': page_num
                            })
                
                # 페이지가 바뀌거나 충분한 항목이 모였을 때 가상 표 생성
                if (page_num != current_page and current_table_items) or len(current_table_items) >= 5:
                    if len(current_table_items) >= 2:  # 최소 2개 항목부터 표로 간주
                        virtual_table = self._create_virtual_table(
                            current_table_items, 
                            current_page, 
                            table_counter
                        )
                        virtual_tables.append(virtual_table)
                        table_counter += 1
                    
                    current_table_items = []
                    current_page = page_num
            
            # 마지막 남은 항목들 처리
            if len(current_table_items) >= 2:
                virtual_table = self._create_virtual_table(
                    current_table_items, 
                    current_page, 
                    table_counter
                )
                virtual_tables.append(virtual_table)
            
            self.logger.info(f"구조화된 텍스트로부터 {len(virtual_tables)}개 가상 표 생성")
            return virtual_tables
            
        except Exception as e:
            self.logger.error(f"구조화된 텍스트 표 변환 실패: {str(e)}")
            return []
    
    def _create_virtual_table(self, items: List[Dict], page_num: int, table_id: int) -> Dict[str, Any]:
        """구조화된 항목들로부터 가상 표 생성"""
        try:
            # 표 데이터 구성
            table_data = []
            cell_texts = []
            
            for i, item in enumerate(items):
                # 각 항목을 행으로 변환
                text = item['text']
                
                # 패턴과 내용 분리
                for pattern in ['①', '②', '③', '④', '⑤', '가)', '나)', '다)', '라)', '마)']:
                    if pattern in text:
                        parts = text.split(pattern, 1)
                        if len(parts) == 2:
                            key = pattern.strip()
                            value = parts[1].strip()
                            table_data.append([key, value])
                            
                            # 셀 텍스트 정보
                            cell_texts.extend([
                                {"text": key, "row": i, "col": 0},
                                {"text": value, "row": i, "col": 1}
                            ])
                        break
                else:
                    # 패턴이 없는 경우 전체 텍스트를 단일 셀로
                    table_data.append([text])
                    cell_texts.append({"text": text, "row": i, "col": 0})
            
            # 추출된 텍스트 생성
            extracted_text = " ".join([item['text'] for item in items])
            
            # 가상 표 메타데이터
            virtual_table = {
                "table_id": f"virtual_table_{table_id:03d}",
                "caption": f"구조화된 텍스트 표 {table_id} (패턴 기반)",
                "page_number": page_num,
                "coordinates": [0, 0, 100, 100],  # 가상 좌표
                "structure": {
                    "rows": len(table_data),
                    "columns": max(len(row) for row in table_data) if table_data else 0
                },
                "table_data": table_data,
                "extracted_text": extracted_text,
                "extraction_tool": "Pattern_Based_Virtual_Table",
                "confidence_score": 0.8,  # 패턴 기반이므로 높은 신뢰도
                "cell_texts": cell_texts,
                "virtual_table": True,  # 가상 표임을 표시
                "source_items": len(items)
            }
            
            return virtual_table
            
        except Exception as e:
            self.logger.error(f"가상 표 생성 실패: {str(e)}")
            return {}

    def _calculate_chunk_statistics(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """청크 통계 계산 - 타입별 상세 분석"""
        try:
            # 타입별 분류
            text_chunks = [c for c in chunks if c.get('type') == 'text']
            table_chunks = [c for c in chunks if c.get('type') == 'table']
            
            # 기본 통계
            stats = {
                "total_chunks": len(chunks),
                "text_chunks_count": len(text_chunks),
                "table_chunks_count": len(table_chunks),
                "text_ratio": round(len(text_chunks) / len(chunks) if chunks else 0, 3),
                "table_ratio": round(len(table_chunks) / len(chunks) if chunks else 0, 3),
                "avg_text_length": round(sum(c.get('word_count', 0) for c in text_chunks) / len(text_chunks) if text_chunks else 0, 1),
                "avg_table_length": round(sum(c.get('word_count', 0) for c in table_chunks) / len(table_chunks) if table_chunks else 0, 1),
                "total_words": sum(c.get('word_count', 0) for c in chunks),
                "total_tokens_estimate": sum(c.get('token_estimate', 0) for c in chunks)
            }
            
            # 타입별 분포
            stats["chunk_type_distribution"] = {
                "text": len(text_chunks),
                "table": len(table_chunks)
            }
            
            # 텍스트 청크 서브타입
            if text_chunks:
                text_subtypes = {}
                for chunk in text_chunks:
                    subtype = chunk.get('subtype', 'unknown')
                    text_subtypes[subtype] = text_subtypes.get(subtype, 0) + 1
                stats["text_chunk_subtypes"] = text_subtypes
            
            # 표 청크 서브타입
            if table_chunks:
                table_subtypes = {}
                for chunk in table_chunks:
                    subtype = chunk.get('subtype', 'unknown')
                    table_subtypes[subtype] = table_subtypes.get(subtype, 0) + 1
                stats["table_chunk_subtypes"] = table_subtypes
            
            # 추출 도구별 통계
            extraction_tools = {}
            for chunk in chunks:
                tool = chunk.get('extraction_tool', 'unknown')
                extraction_tools[tool] = extraction_tools.get(tool, 0) + 1
            stats["extraction_tools_used"] = extraction_tools
            
            # 표 신뢰도 통계
            table_confidences = [c.get('confidence_score', 0) for c in table_chunks if 'confidence_score' in c]
            if table_confidences:
                stats["table_confidence_stats"] = {
                    "average": round(sum(table_confidences) / len(table_confidences), 3),
                    "min": round(min(table_confidences), 3),
                    "max": round(max(table_confidences), 3),
                    "count": len(table_confidences)
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"청크 통계 계산 실패: {str(e)}")
            return {
                "total_chunks": len(chunks),
                "text_chunks_count": 0,
                "table_chunks_count": 0,
                "error": str(e)
            }
    
    def cleanup(self):
        """리소스 정리"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            self.logger.info("리소스 정리 완료")
        except Exception as e:
            self.logger.error(f"리소스 정리 오류: {str(e)}")
    
    def __del__(self):
        """소멸자"""
        self.cleanup() 