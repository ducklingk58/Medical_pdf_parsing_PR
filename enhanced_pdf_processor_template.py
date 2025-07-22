"""
향상된 Medical PDF 파싱 프로세서 (JSON 템플릿 준수)
Unstructured 텍스트 파싱 + LayoutParser/PaddleOCR 고급 테이블/이미지 파싱
제공된 JSON 템플릿에 정확히 맞는 출력 생성
"""

import os
import re
import json
import pandas as pd
import io
import time
import traceback
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from unstructured.partition.auto import partition
from unstructured.documents.elements import Table, Title, NarrativeText, Image
import logging
from tqdm import tqdm
import concurrent.futures
from datetime import datetime

# 고급 파싱 모듈 import
from utils.advanced_parser import AdvancedParser
from utils.enhanced_metadata_generator import EnhancedMetadataGenerator
from config.settings import Settings
from utils.logger import setup_logger, log_file_processing

class EnhancedPDFProcessorTemplate:
    """향상된 PDF 처리기 - 제공된 JSON 템플릿 준수"""
    
    def __init__(self, use_gpu: bool = False, similarity_threshold: float = None):
        self.similarity_threshold = similarity_threshold or Settings.SIMILARITY_THRESHOLD
        self.sentence_model = SentenceTransformer(Settings.SENTENCE_MODEL)
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # 고급 파싱기 초기화
        self.advanced_parser = AdvancedParser(use_gpu=use_gpu)
        
        # 메타데이터 생성기 초기화
        self.metadata_generator = EnhancedMetadataGenerator()
        
        self.logger.info(f"향상된 PDF 처리기 초기화 완료 (GPU: {use_gpu})")
    
    def partition_pdf_text_only(self, pdf_path: str) -> List:
        """Unstructured를 사용한 텍스트 전용 파싱 (테이블/이미지 추출 비활성화)"""
        try:
            self.logger.info(f"텍스트 전용 PDF 파싱 시작: {pdf_path}")
            elements = partition(
                filename=pdf_path,
                include_image_metadata=False,  # 이미지 메타데이터 비활성화
                extract_tables=False,          # 테이블 추출 비활성화
                pdf_extract_images=False,      # 이미지 추출 비활성화
                strategy="fast"
            )
            self.logger.info(f"텍스트 파싱 완료: {len(elements)}개 요소 추출")
            return elements
        except Exception as e:
            self.logger.error(f"텍스트 파싱 오류: {str(e)}")
            raise
    
    def clean_text(self, text: str) -> str:
        """텍스트 정제 - 헤더/푸터, 페이지 번호 제거"""
        if not text:
            return ""
        
        # 페이지 번호 패턴 제거
        if Settings.REMOVE_PAGE_NUMBERS:
            text = re.sub(r'---\s*PAGE\s+\d+\s*---', '', text, flags=re.IGNORECASE)
            text = re.sub(r'-\s*\d+\s*-', '', text)
            text = re.sub(r'페이지\s*\d+', '', text)
            text = re.sub(r'Page\s+\d+', '', text, flags=re.IGNORECASE)
        
        # 반복되는 헤더/푸터 제거
        if Settings.REMOVE_HEADERS_FOOTERS:
            text = re.sub(r'MFDS/MaPP.*?\n', '', text, flags=re.IGNORECASE)
            text = re.sub(r'의약품안전관리.*?\n', '', text)
            text = re.sub(r'식품의약품안전처.*?\n', '', text)
        
        # 불필요한 공백 정리
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\t+', ' ', text)
        
        return text.strip()
    
    def extract_text_elements(self, elements: List) -> List[Dict[str, Any]]:
        """텍스트 요소 추출 및 정제 (페이지 정보 포함)"""
        text_elements = []
        
        for element in elements:
            if isinstance(element, (NarrativeText, Title)):
                cleaned_text = self.clean_text(element.text)
                if cleaned_text:
                    # 페이지 번호 추출
                    page_numbers = self._extract_page_numbers_from_element(element)
                    
                    element_info = {
                        "text": cleaned_text,
                        "type": "Title" if isinstance(element, Title) else "NarrativeText",
                        "page_numbers": page_numbers,
                        "element": element
                    }
                    text_elements.append(element_info)
        
        self.logger.info(f"총 {len(text_elements)}개 텍스트 요소 추출 완료")
        return text_elements
    
    def _extract_page_numbers_from_element(self, element) -> List[int]:
        """요소에서 페이지 번호 추출"""
        try:
            if hasattr(element, 'metadata') and element.metadata:
                if hasattr(element.metadata, 'page_number'):
                    return [element.metadata.page_number]
                elif hasattr(element.metadata, 'page_numbers'):
                    return element.metadata.page_numbers
        except:
            pass
        
        # 기본값
        return [1]
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """두 텍스트 간 코사인 유사도 계산"""
        try:
            embeddings = self.sentence_model.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            self.logger.warning(f"유사도 계산 오류: {str(e)}")
            return 0.0
    
    def connect_sentences(self, text_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """의미론적 유사도 기반 문장 연결"""
        if not text_elements:
            return []
        
        self.logger.info("문장 연결 프로세스 시작...")
        connected_blocks = []
        current_block = text_elements[0]
        
        for i in range(1, len(text_elements)):
            current_element = text_elements[i]
            
            # 논리적 단절 지점 식별
            is_break_point = self._is_logical_break(current_block["text"], current_element["text"])
            
            if is_break_point:
                # 단절 지점이면 새 블록 시작
                if current_block["text"].strip():
                    connected_blocks.append(current_block)
                current_block = current_element
            else:
                # 유사도 계산
                similarity = self.calculate_similarity(current_block["text"], current_element["text"])
                
                if similarity >= self.similarity_threshold:
                    # 유사도가 높으면 연결
                    current_block["text"] += "\n\n" + current_element["text"]
                    # 페이지 번호 병합
                    current_block["page_numbers"] = list(set(current_block["page_numbers"] + current_element["page_numbers"]))
                else:
                    # 유사도가 낮으면 새 블록 시작
                    if current_block["text"].strip():
                        connected_blocks.append(current_block)
                    current_block = current_element
        
        # 마지막 블록 추가
        if current_block["text"].strip():
            connected_blocks.append(current_block)
        
        self.logger.info(f"문장 연결 완료: {len(connected_blocks)}개 블록 생성")
        return connected_blocks
    
    def _is_logical_break(self, text1: str, text2: str) -> bool:
        """논리적 단절 지점 식별"""
        # 제목 패턴 확인
        if re.match(r'^[A-Z][A-Z\s]+$', text2.strip()):
            return True
        
        # 번호 패턴 확인
        if re.match(r'^\d+\.\s', text2.strip()):
            return True
        
        # 소제목 패턴 확인
        if re.match(r'^[가-힣\s]+:$', text2.strip()):
            return True
        
        # 짧은 텍스트는 단절 가능성 높음
        if len(text2.strip()) < 20:
            return True
        
        return False
    
    def create_rag_chunks(self, text_blocks: List[Dict[str, Any]], 
                         chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """RAG 친화적 청킹 생성"""
        chunk_size = chunk_size or Settings.CHUNK_SIZE
        overlap = overlap or Settings.CHUNK_OVERLAP
        
        chunks = []
        
        for block in text_blocks:
            # 문장 단위로 분할
            sentences = re.split(r'[.!?]+', block["text"])
            
            current_chunk_text = ""
            current_chunk_pages = block["page_numbers"].copy()
            
            for sentence in sentences:
                if len(current_chunk_text) + len(sentence) <= chunk_size:
                    current_chunk_text += sentence + " "
                else:
                    if current_chunk_text.strip():
                        chunk_info = {
                            "text": current_chunk_text.strip(),
                            "type": block["type"],
                            "page_numbers": current_chunk_pages,
                            "token_estimate": len(current_chunk_text.split()),
                            "element": block.get("element")
                        }
                        chunks.append(chunk_info)
                    current_chunk_text = sentence + " "
                    current_chunk_pages = block["page_numbers"].copy()
            
            if current_chunk_text.strip():
                chunk_info = {
                    "text": current_chunk_text.strip(),
                    "type": block["type"],
                    "page_numbers": current_chunk_pages,
                    "token_estimate": len(current_chunk_text.split()),
                    "element": block.get("element")
                }
                chunks.append(chunk_info)
        
        # 중복 제거 및 정리
        final_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0 and overlap > 0:
                # 이전 청크와 중복 추가
                prev_text = chunks[i-1]["text"]
                overlap_text = " ".join(prev_text.split()[-overlap:])
                chunk["text"] = overlap_text + " " + chunk["text"]
            
            final_chunks.append(chunk)
        
        self.logger.info(f"RAG 청킹 완료: {len(final_chunks)}개 청크 생성")
        return final_chunks
    
    def save_advanced_tables(self, extracted_tables: List[Dict], output_dir: Path, 
                           original_filename: str) -> List[str]:
        """고급 파싱으로 추출된 테이블 저장 (파일명 규칙 준수)"""
        table_files = []
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        for i, table in enumerate(extracted_tables):
            table_id = f"{original_filename}_table_{i+1:03d}"
            page_num = table.get("page_number", 1)
            
            # JSON 형태로 저장
            json_path = tables_dir / f"{table_id}_page_{page_num}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2, default=str)
            
            # CSV 형태로도 저장 (DataFrame이 있는 경우)
            if "dataframe" in table and table["dataframe"] is not None:
                csv_path = tables_dir / f"{table_id}_page_{page_num}.csv"
                table["dataframe"].to_csv(csv_path, index=False, encoding='utf-8-sig')
                table_files.append(str(csv_path))
            
            # Excel 형태로도 저장
            if "dataframe" in table and table["dataframe"] is not None:
                excel_path = tables_dir / f"{table_id}_page_{page_num}.xlsx"
                table["dataframe"].to_excel(excel_path, index=False, engine='openpyxl')
            
            # HTML 형태로도 저장
            if "html" in table:
                html_path = tables_dir / f"{table_id}_page_{page_num}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(table["html"])
        
        self.logger.info(f"고급 테이블 데이터 저장 완료: {len(table_files)}개 파일")
        return table_files
    
    def save_advanced_images(self, extracted_images: List[Dict], output_dir: Path,
                           original_filename: str) -> List[str]:
        """고급 파싱으로 추출된 이미지 저장 (파일명 규칙 준수)"""
        image_files = []
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        for i, image in enumerate(extracted_images):
            image_id = f"{original_filename}_image_{i+1:03d}"
            page_num = image.get("page_number", 1)
            
            # 이미지 파일 저장
            if "image_data" in image:
                image_path = images_dir / f"{image_id}_page_{page_num}.png"
                with open(image_path, 'wb') as f:
                    f.write(image["image_data"])
                image_files.append(str(image_path))
            
            # 메타데이터 JSON 저장
            metadata_path = images_dir / f"{image_id}_page_{page_num}_metadata.json"
            metadata = {k: v for k, v in image.items() if k != "image_data"}
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
        
        self.logger.info(f"고급 이미지 데이터 저장 완료: {len(image_files)}개 파일")
        return image_files
    
    def create_enhanced_markdown(self, text_blocks: List[Dict[str, Any]], 
                                table_files: List[str], image_files: List[str], 
                                output_dir: Path, original_filename: str) -> str:
        """향상된 마크다운 파일 생성 (파일명 규칙 준수)"""
        md_content = []
        
        # 문서 제목
        md_content.append(f"# {original_filename}\n\n")
        
        # 텍스트 블록 추가
        for i, block in enumerate(text_blocks):
            if block["type"] == "Title":
                md_content.append(f"## {block['text']}\n\n")
            else:
                md_content.append(f"{block['text']}\n\n")
        
        # 고급 테이블 참조 추가
        if table_files:
            md_content.append("## 추출된 테이블 (고급 파싱)\n")
            for table_file in table_files:
                table_name = Path(table_file).stem
                table_dir = Path(table_file).parent
                
                # CSV 파일 링크
                md_content.append(f"- [테이블 데이터 (CSV): {table_name}]({table_file})\n")
                
                # Excel 파일이 있으면 링크 추가
                excel_file = table_dir / f"{table_name}.xlsx"
                if excel_file.exists():
                    md_content.append(f"- [테이블 데이터 (Excel): {table_name}]({excel_file})\n")
                
                # HTML 파일이 있으면 링크 추가
                html_file = table_dir / f"{table_name}.html"
                if html_file.exists():
                    md_content.append(f"- [테이블 데이터 (HTML): {table_name}]({html_file})\n")
            md_content.append("\n")
        
        # 고급 이미지 참조 추가
        if image_files:
            md_content.append("## 추출된 이미지 (고급 파싱)\n")
            for image_file in image_files:
                image_name = Path(image_file).stem
                image_dir = Path(image_file).parent
                
                # 이미지 표시
                md_content.append(f"![{image_name}]({image_file})\n")
                
                # 메타데이터 파일이 있으면 링크 추가
                metadata_file = image_dir / f"{image_name}_metadata.json"
                if metadata_file.exists():
                    md_content.append(f"- [이미지 메타데이터: {image_name}]({metadata_file})\n")
            md_content.append("\n")
        
        md_path = output_dir / f"{original_filename}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(''.join(md_content))
        
        self.logger.info(f"향상된 마크다운 파일 생성 완료: {md_path}")
        return str(md_path)
    
    def generate_template_metadata(self, original_filename: str, 
                                 text_chunks: List[Dict[str, Any]],
                                 table_files: List[str], 
                                 image_files: List[str]) -> List[Dict[str, Any]]:
        """제공된 JSON 템플릿에 맞는 메타데이터 생성"""
        
        metadata_list = []
        
        # 텍스트 청크 메타데이터 생성
        for i, chunk in enumerate(text_chunks):
            chunk_id = f"{original_filename}_chunk_{i+1:03d}"
            
            # 섹션 제목 추출 (이전 제목 요소에서)
            section_title = None
            if i > 0 and text_chunks[i-1]["type"] == "Title":
                section_title = text_chunks[i-1]["text"]
            
            # 관련 테이블/이미지 참조 찾기
            table_refs = []
            image_refs = []
            
            # 페이지 번호 기반으로 관련 파일 찾기
            chunk_pages = chunk["page_numbers"]
            for table_file in table_files:
                if any(str(page) in table_file for page in chunk_pages):
                    table_refs.append(table_file)
            
            for image_file in image_files:
                if any(str(page) in image_file for page in chunk_pages):
                    image_refs.append(image_file)
            
            chunk_metadata = self.metadata_generator.create_text_chunk_metadata(
                chunk_id=chunk_id,
                original_file_name=f"{original_filename}.pdf",
                text_content=chunk["text"],
                page_numbers=chunk["page_numbers"],
                section_title=section_title,
                table_refs=table_refs,
                image_refs=image_refs
            )
            metadata_list.append(chunk_metadata)
        
        return metadata_list
    
    def process_pdf_template(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """제공된 JSON 템플릿에 맞는 PDF 처리 메인 프로세스"""
        try:
            self.logger.info(f"향상된 PDF 처리 시작: {pdf_path}")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            start_time = time.time()
            original_filename = Path(pdf_path).stem
            
            # 1. Unstructured를 사용한 텍스트 전용 파싱
            self.logger.info("1단계: Unstructured 텍스트 파싱")
            elements = self.partition_pdf_text_only(pdf_path)
            text_elements = self.extract_text_elements(elements)
            
            # 2. 고급 파싱 (LayoutParser + PaddleOCR)
            self.logger.info("2단계: 고급 테이블/이미지 파싱")
            advanced_result = self.advanced_parser.process_pdf_advanced(pdf_path, str(output_path))
            
            # 3. 텍스트 정제 및 문장 연결
            self.logger.info("3단계: 텍스트 정제 및 문장 연결")
            connected_blocks = self.connect_sentences(text_elements)
            
            # 4. RAG 청킹
            self.logger.info("4단계: RAG 청킹")
            rag_chunks = self.create_rag_chunks(connected_blocks)
            
            # 5. 고급 테이블/이미지 저장 (파일명 규칙 준수)
            self.logger.info("5단계: 고급 테이블/이미지 저장")
            table_files = self.save_advanced_tables(advanced_result["extracted_tables"], 
                                                   output_path, original_filename)
            image_files = self.save_advanced_images(advanced_result["extracted_images"], 
                                                   output_path, original_filename)
            
            # 6. 향상된 마크다운 생성 (파일명 규칙 준수)
            self.logger.info("6단계: 향상된 마크다운 생성")
            md_file = self.create_enhanced_markdown(rag_chunks, table_files, 
                                                   image_files, output_path, original_filename)
            
            # 7. 제공된 JSON 템플릿에 맞는 메타데이터 생성
            self.logger.info("7단계: JSON 템플릿 메타데이터 생성")
            template_metadata = self.generate_template_metadata(
                original_filename, rag_chunks, table_files, image_files
            )
            
            # 메타데이터 저장
            metadata_path = output_path / "metadata.json"
            self.metadata_generator.save_metadata(template_metadata, metadata_path)
            
            # 8. 요약 생성
            self.logger.info("8단계: 요약 생성")
            processing_time = time.time() - start_time
            summary = self.metadata_generator.create_summary_metadata(
                original_file_name=f"{original_filename}.pdf",
                text_chunks_count=len(rag_chunks),
                table_files_count=len(table_files),
                image_files_count=len(image_files),
                total_pages=advanced_result.get("total_pages", 1),
                processing_time=processing_time
            )
            summary_path = output_path / "summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"향상된 PDF 처리 완료: {processing_time:.2f}초")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"향상된 PDF 처리 실패: {str(e)}")
            raise
    
    def cleanup(self):
        """리소스 정리"""
        if hasattr(self, 'advanced_parser'):
            self.advanced_parser.cleanup()
    
    def __del__(self):
        """소멸자에서 정리"""
        self.cleanup()

class EnhancedBatchProcessorTemplate:
    """향상된 배치 처리기 - JSON 템플릿 준수"""
    
    def __init__(self, input_dir: str = None, output_dir: str = None, 
                 max_workers: int = None, use_gpu: bool = False):
        self.input_dir = Path(input_dir) if input_dir else Settings.INPUT_DIR
        self.output_dir = Path(output_dir) if output_dir else Settings.OUTPUT_DIR
        self.max_workers = max_workers or Settings.MAX_WORKERS
        self.use_gpu = use_gpu
        self.logger = setup_logger()
        
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)
        
        self.logger.info(f"향상된 배치 프로세서 초기화 완료")
        self.logger.info(f"입력 디렉토리: {self.input_dir}")
        self.logger.info(f"출력 디렉토리: {self.output_dir}")
        self.logger.info(f"최대 워커 수: {self.max_workers}")
        self.logger.info(f"GPU 사용: {use_gpu}")
    
    def get_pdf_files(self) -> List[Path]:
        """PDF 파일 목록 가져오기"""
        pdf_files = list(self.input_dir.glob("*.pdf"))
        self.logger.info(f"발견된 PDF 파일: {len(pdf_files)}개")
        return pdf_files
    
    def process_single_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """단일 PDF 처리"""
        result = {
            "filename": pdf_path.name,
            "filepath": str(pdf_path),
            "status": "success",
            "error": None,
            "summary": {},
            "processing_time": 0,
            "timestamp": time.time()
        }
        
        start_time = time.time()
        
        try:
            file_logger = self.logger
            output_subdir = self.output_dir / pdf_path.stem
            
            # 향상된 PDF 처리기 생성
            processor = EnhancedPDFProcessorTemplate(use_gpu=self.use_gpu)
            
            summary = processor.process_pdf_template(
                pdf_path=str(pdf_path),
                output_dir=str(output_subdir)
            )
            
            result["summary"] = summary
            result["processing_time"] = time.time() - start_time
            
            log_file_processing(
                file_logger, 
                pdf_path.name, 
                "success", 
                f"처리 시간: {result['processing_time']:.2f}초, "
                f"텍스트 청크: {summary.get('statistics', {}).get('text_chunks_count', 0)}, "
                f"테이블: {summary.get('statistics', {}).get('table_files_count', 0)}, "
                f"이미지: {summary.get('statistics', {}).get('image_files_count', 0)}",
                None
            )
            
            # 리소스 정리
            processor.cleanup()
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            
            error_log_path = self.output_dir / "logs" / f"error_{pdf_path.stem}.txt"
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(f"파일: {pdf_path.name}\n")
                f.write(f"경로: {pdf_path}\n")
                f.write(f"오류: {str(e)}\n")
                f.write(f"처리 시간: {result['processing_time']:.2f}초\n")
                f.write(f"상세 정보:\n{traceback.format_exc()}\n")
            
            log_file_processing(
                self.logger, 
                pdf_path.name, 
                "error", 
                f"처리 시간: {result['processing_time']:.2f}초", 
                str(e)
            )
        
        return result
    
    def process_all_pdfs(self) -> Dict[str, Any]:
        """모든 PDF 처리"""
        pdf_files = self.get_pdf_files()
        
        if not pdf_files:
            self.logger.warning("처리할 PDF 파일이 없습니다.")
            return {"total_files": 0, "successful_files": 0, "failed_files": 0}
        
        self.logger.info(f"총 {len(pdf_files)}개 PDF 파일 처리 시작")
        
        results = []
        
        # 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.process_single_pdf, pdf_file): pdf_file 
                            for pdf_file in pdf_files}
            
            with tqdm(total=len(pdf_files), desc="PDF 처리 진행률") as pbar:
                for future in concurrent.futures.as_completed(future_to_file):
                    result = future.result()
                    results.append(result)
                    pbar.update(1)
                    
                    if result["status"] == "success":
                        pbar.set_postfix({"성공": len([r for r in results if r["status"] == "success"])})
                    else:
                        pbar.set_postfix({"실패": len([r for r in results if r["status"] == "error"])})
        
        # 결과 요약
        successful_files = [r for r in results if r["status"] == "success"]
        failed_files = [r for r in results if r["status"] == "error"]
        
        summary = {
            "total_files": len(pdf_files),
            "successful_files": len(successful_files),
            "failed_files": len(failed_files),
            "success_rate": len(successful_files) / len(pdf_files),
            "total_processing_time": sum(r["processing_time"] for r in results),
            "average_processing_time": sum(r["processing_time"] for r in results) / len(results),
            "results": results
        }
        
        # 배치 요약 저장
        batch_summary_path = self.output_dir / "enhanced_batch_summary_template.json"
        with open(batch_summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        
        self._print_detailed_statistics(summary)
        return summary
    
    def _print_detailed_statistics(self, summary: Dict[str, Any]):
        """상세 통계 출력"""
        self.logger.info("=" * 80)
        self.logger.info("향상된 PDF 파싱 결과 요약 (JSON 템플릿 준수)")
        self.logger.info("=" * 80)
        self.logger.info(f"총 파일 수: {summary['total_files']}")
        self.logger.info(f"성공한 파일 수: {summary['successful_files']}")
        self.logger.info(f"실패한 파일 수: {summary['failed_files']}")
        self.logger.info(f"성공률: {summary['success_rate']:.2%}")
        self.logger.info(f"총 처리 시간: {summary['total_processing_time']:.2f}초")
        self.logger.info(f"평균 처리 시간: {summary['average_processing_time']:.2f}초/파일")
        
        # 성공한 파일들의 상세 통계
        if summary['successful_files'] > 0:
            successful_results = [r for r in summary['results'] if r['status'] == 'success']
            
            total_text_chunks = sum(r['summary'].get('statistics', {}).get('text_chunks_count', 0) for r in successful_results)
            total_tables = sum(r['summary'].get('statistics', {}).get('table_files_count', 0) for r in successful_results)
            total_images = sum(r['summary'].get('statistics', {}).get('image_files_count', 0) for r in successful_results)
            
            self.logger.info(f"총 추출된 텍스트 청크: {total_text_chunks}")
            self.logger.info(f"총 추출된 테이블: {total_tables}")
            self.logger.info(f"총 추출된 이미지: {total_images}")
        
        self.logger.info("=" * 80)

if __name__ == "__main__":
    # 사용 예시
    processor = EnhancedBatchProcessorTemplate(use_gpu=False)
    summary = processor.process_all_pdfs()
    print("처리 완료!") 