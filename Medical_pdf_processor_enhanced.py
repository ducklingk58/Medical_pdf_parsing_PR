"""
향상된 Medical PDF 파싱 프로세서
Unstructured 텍스트 파싱 + LayoutParser/PaddleOCR 고급 테이블/이미지 파싱 통합
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
from config.settings import Settings
from utils.logger import setup_logger, log_file_processing

class EnhancedPDFProcessor:
    """향상된 PDF 처리기 - Unstructured + LayoutParser/PaddleOCR 통합"""
    
    def __init__(self, use_gpu: bool = False, similarity_threshold: float = None):
        self.similarity_threshold = similarity_threshold or Settings.SIMILARITY_THRESHOLD
        self.sentence_model = SentenceTransformer(Settings.SENTENCE_MODEL)
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # 고급 파싱기 초기화
        self.advanced_parser = AdvancedParser(use_gpu=use_gpu)
        
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
    
    def extract_text_elements(self, elements: List) -> List[str]:
        """텍스트 요소 추출 및 정제"""
        text_elements = []
        
        for element in elements:
            if isinstance(element, (NarrativeText, Title)):
                cleaned_text = self.clean_text(element.text)
                if cleaned_text:
                    text_elements.append(cleaned_text)
        
        self.logger.info(f"총 {len(text_elements)}개 텍스트 요소 추출 완료")
        return text_elements
    
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
    
    def connect_sentences(self, text_elements: List[str]) -> List[str]:
        """의미론적 유사도 기반 문장 연결"""
        if not text_elements:
            return []
        
        self.logger.info("문장 연결 프로세스 시작...")
        connected_blocks = []
        current_block = text_elements[0]
        
        for i in range(1, len(text_elements)):
            current_text = text_elements[i]
            
            # 논리적 단절 지점 식별
            is_break_point = self._is_logical_break(current_block, current_text)
            
            if is_break_point:
                # 단절 지점이면 새 블록 시작
                if current_block.strip():
                    connected_blocks.append(current_block.strip())
                current_block = current_text
            else:
                # 유사도 계산
                similarity = self.calculate_similarity(current_block, current_text)
                
                if similarity >= self.similarity_threshold:
                    # 유사도가 높으면 연결
                    current_block += "\n\n" + current_text
                else:
                    # 유사도가 낮으면 새 블록 시작
                    if current_block.strip():
                        connected_blocks.append(current_block.strip())
                    current_block = current_text
        
        # 마지막 블록 추가
        if current_block.strip():
            connected_blocks.append(current_block.strip())
        
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
    
    def create_rag_chunks(self, text_blocks: List[str], chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """RAG 친화적 청킹 생성"""
        chunk_size = chunk_size or Settings.CHUNK_SIZE
        overlap = overlap or Settings.CHUNK_OVERLAP
        
        chunks = []
        
        for block in text_blocks:
            # 문장 단위로 분할
            sentences = re.split(r'[.!?]+', block)
            
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += sentence + " "
                else:
                    if current_chunk.strip():
                        chunks.append({
                            "text": current_chunk.strip(),
                            "token_estimate": len(current_chunk.split()),
                            "type": "text_chunk"
                        })
                    current_chunk = sentence + " "
            
            if current_chunk.strip():
                chunks.append({
                    "text": current_chunk.strip(),
                    "token_estimate": len(current_chunk.split()),
                    "type": "text_chunk"
                })
        
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
    
    def save_advanced_tables(self, extracted_tables: List[Dict], output_dir: Path) -> List[str]:
        """고급 파싱으로 추출된 테이블 저장"""
        table_files = []
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        for table in extracted_tables:
            table_id = table.get("table_id", f"table_{len(table_files)+1:03d}")
            
            # JSON 형태로 저장
            json_path = tables_dir / f"{table_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2, default=str)
            
            # CSV 형태로도 저장 (DataFrame이 있는 경우)
            if "dataframe" in table and table["dataframe"] is not None:
                csv_path = tables_dir / f"{table_id}.csv"
                table["dataframe"].to_csv(csv_path, index=False, encoding='utf-8-sig')
                
                # Excel 형태로도 저장
                excel_path = tables_dir / f"{table_id}.xlsx"
                table["dataframe"].to_excel(excel_path, index=False, engine='openpyxl')
            
            # HTML 형태로도 저장
            if "html" in table:
                html_path = tables_dir / f"{table_id}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(table["html"])
            
            table_files.append(str(json_path))
        
        self.logger.info(f"고급 테이블 데이터 저장 완료: {len(table_files)}개 파일")
        return table_files
    
    def save_advanced_images(self, extracted_images: List[Dict], output_dir: Path) -> List[str]:
        """고급 파싱으로 추출된 이미지 저장"""
        image_files = []
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        for image in extracted_images:
            image_id = image.get("image_id", f"image_{len(image_files)+1:03d}")
            
            # 이미지 파일 저장
            if "image_data" in image:
                image_path = images_dir / f"{image_id}.png"
                with open(image_path, 'wb') as f:
                    f.write(image["image_data"])
            
            # 메타데이터 JSON 저장
            metadata_path = images_dir / f"{image_id}_metadata.json"
            metadata = {k: v for k, v in image.items() if k != "image_data"}
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
            
            image_files.append(str(metadata_path))
        
        self.logger.info(f"고급 이미지 데이터 저장 완료: {len(image_files)}개 파일")
        return image_files
    
    def create_enhanced_markdown(self, text_blocks: List[str], table_files: List[str], 
                                image_files: List[str], output_dir: Path) -> str:
        """향상된 마크다운 파일 생성"""
        md_content = []
        
        # 텍스트 블록 추가
        for i, block in enumerate(text_blocks):
            md_content.append(f"## 텍스트 블록 {i+1}\n")
            md_content.append(block)
            md_content.append("\n\n")
        
        # 고급 테이블 참조 추가
        if table_files:
            md_content.append("## 추출된 테이블 (고급 파싱)\n")
            for table_file in table_files:
                table_name = Path(table_file).stem
                table_dir = Path(table_file).parent
                
                # CSV 파일이 있으면 링크 추가
                csv_file = table_dir / f"{table_name}.csv"
                if csv_file.exists():
                    md_content.append(f"- [테이블 데이터 (CSV): {table_name}]({csv_file.relative_to(output_dir)})\n")
                
                # Excel 파일이 있으면 링크 추가
                excel_file = table_dir / f"{table_name}.xlsx"
                if excel_file.exists():
                    md_content.append(f"- [테이블 데이터 (Excel): {table_name}]({excel_file.relative_to(output_dir)})\n")
                
                # HTML 파일이 있으면 링크 추가
                html_file = table_dir / f"{table_name}.html"
                if html_file.exists():
                    md_content.append(f"- [테이블 데이터 (HTML): {table_name}]({html_file.relative_to(output_dir)})\n")
                
                # JSON 메타데이터 링크
                md_content.append(f"- [테이블 메타데이터: {table_name}]({table_file})\n")
            md_content.append("\n")
        
        # 고급 이미지 참조 추가
        if image_files:
            md_content.append("## 추출된 이미지 (고급 파싱)\n")
            for image_file in image_files:
                image_name = Path(image_file).stem.replace("_metadata", "")
                image_dir = Path(image_file).parent
                
                # 실제 이미지 파일 링크
                image_path = image_dir / f"{image_name}.png"
                if image_path.exists():
                    md_content.append(f"![{image_name}]({image_path.relative_to(output_dir)})\n")
                
                # 메타데이터 링크
                md_content.append(f"- [이미지 메타데이터: {image_name}]({image_file})\n")
            md_content.append("\n")
        
        md_path = output_dir / "enhanced_markdown.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(''.join(md_content))
        
        self.logger.info(f"향상된 마크다운 파일 생성 완료: {md_path}")
        return str(md_path)
    
    def create_enhanced_summary(self, text_blocks: List[str], extracted_tables: List[Dict], 
                               extracted_images: List[Dict], chunks: List[Dict]) -> Dict[str, Any]:
        """향상된 파싱 결과 요약 생성"""
        total_words = sum(len(block.split()) for block in text_blocks)
        total_tokens = sum(chunk.get("token_estimate", 0) for chunk in chunks)
        
        # 테이블 통계
        table_stats = {
            "total_tables": len(extracted_tables),
            "tables_with_dataframe": len([t for t in extracted_tables if t.get("dataframe") is not None]),
            "tables_with_html": len([t for t in extracted_tables if t.get("html")]),
            "total_table_rows": sum(t.get("shape", [0, 0])[0] for t in extracted_tables if t.get("shape")),
            "total_table_columns": sum(t.get("shape", [0, 0])[1] for t in extracted_tables if t.get("shape"))
        }
        
        # 이미지 통계
        image_stats = {
            "total_images": len(extracted_images),
            "images_with_data": len([i for i in extracted_images if i.get("image_data")]),
            "total_image_size_mb": sum(i.get("size", 0) for i in extracted_images) / (1024 * 1024)
        }
        
        summary = {
            "success": True,  # 성공 상태 필드 추가
            "text_blocks_count": len(text_blocks),
            "rag_chunks_count": len(chunks),
            "total_words": total_words,
            "total_tokens_estimate": total_tokens,
            "table_statistics": table_stats,
            "image_statistics": image_stats,
            "processing_timestamp": pd.Timestamp.now().isoformat(),
            "processing_method": "Enhanced (Unstructured + Table Transformer)",
            "settings": {
                "similarity_threshold": self.similarity_threshold,
                "chunk_size": Settings.CHUNK_SIZE,
                "chunk_overlap": Settings.CHUNK_OVERLAP,
                "use_gpu": self.use_gpu
            }
        }
        
        return summary
    
    def process_pdf_enhanced(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """향상된 PDF 처리 메인 프로세스"""
        try:
            self.logger.info(f"향상된 PDF 처리 시작: {pdf_path}")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            start_time = time.time()
            
            # 1단계: 일반 텍스트 파싱 (Unstructured)
            self.logger.info("1단계: 일반 텍스트 파싱 (Unstructured)")
            print("🔤 일반 텍스트 추출 중...")
            elements = self.partition_pdf_text_only(pdf_path)
            text_elements = self.extract_text_elements(elements)
            print(f"   ✅ {len(text_elements)}개 텍스트 요소 추출 완료")
            
            # 2단계: 표 및 이미지 파싱 (Table Transformer + LayoutParser)
            self.logger.info("2단계: 표 및 이미지 파싱 (Table Transformer + LayoutParser)")
            print("📊 표 데이터 파싱 중 (Table Transformer)...")
            advanced_result = self.advanced_parser.process_pdf_advanced(pdf_path, str(output_path))
            print(f"   ✅ {len(advanced_result.get('tables', []))}개 표, {len(advanced_result.get('images', []))}개 이미지 추출 완료")
            
            # 3단계: 텍스트 정제 및 문장 연결
            self.logger.info("3단계: 텍스트 정제 및 문장 연결")
            print("🔗 텍스트 블록 연결 중...")
            connected_blocks = self.connect_sentences(text_elements)
            print(f"   ✅ {len(connected_blocks)}개 연결된 텍스트 블록 생성")
            
            # 4단계: RAG 청킹
            self.logger.info("4단계: RAG 청킹")
            print("✂️ RAG 최적화 청킹 중...")
            rag_chunks = self.create_rag_chunks(connected_blocks)
            print(f"   ✅ {len(rag_chunks)}개 RAG 청크 생성")
            
            # 5단계: 파일 저장 및 구조화
            self.logger.info("5단계: 파일 저장 및 구조화")
            print("💾 결과 파일 저장 중...")
            table_files = self.save_advanced_tables(advanced_result["tables"], output_path)
            image_files = self.save_advanced_images(advanced_result["images"], output_path)
            
            # 6단계: 마크다운 생성
            self.logger.info("6단계: 마크다운 생성")
            md_file = self.create_enhanced_markdown(connected_blocks, table_files, image_files, output_path)
            
            # 7단계: 구조화된 JSON 생성 (사용자 스키마 적용)
            self.logger.info("7단계: 구조화된 JSON 생성 (사용자 스키마 적용)")
            print("📄 구조화된 JSON 결과 생성 중...")
            
            # 기존 구조화된 JSON 생성기 사용
            try:
                from utils.structured_json_generator import create_structured_json
                
                # 텍스트 청크와 표 데이터로부터 구조화된 문서 생성
                structured_document = create_structured_json(
                    text_chunks=rag_chunks,  # RAG 청크 사용
                    extracted_tables=advanced_result["tables"],
                    source_file=pdf_path
                )
                
                # 구조화된 문서 저장
                structured_path = output_path / "structured_document.json"
                with open(structured_path, 'w', encoding='utf-8') as f:
                    json.dump(structured_document, f, ensure_ascii=False, indent=2, default=str)
                print(f"   ✅ 구조화된 문서 저장: {structured_path}")
                
            except ImportError:
                self.logger.warning("구조화된 JSON 생성기를 찾을 수 없습니다.")
                print("   ⚠️ 구조화된 JSON 생성 실패, 기본 형태로 저장")
            
            # 사용자 정의 스키마 JSON 생성 (새로 추가)
            try:
                from utils.user_schema_generator import create_user_schema_json
                
                print("📋 사용자 정의 스키마 JSON 생성 중...")
                
                # 사용자 스키마에 맞는 배열 형태 JSON 생성
                user_schema_json = create_user_schema_json(
                    text_chunks=rag_chunks,  # RAG 청크 사용
                    extracted_tables=advanced_result["tables"],
                    source_file=pdf_path
                )
                
                # 사용자 스키마 JSON 저장
                user_schema_path = output_path / "user_schema_output.json"
                with open(user_schema_path, 'w', encoding='utf-8') as f:
                    json.dump(user_schema_json, f, ensure_ascii=False, indent=2, default=str)
                print(f"   ✅ 사용자 정의 스키마 JSON 저장: {user_schema_path}")
                
            except ImportError:
                self.logger.warning("사용자 스키마 JSON 생성기를 찾을 수 없습니다.")
                print("   ⚠️ 사용자 스키마 JSON 생성 실패")
                
                # 기본 메타데이터 (text_blocks 제외)
                metadata = {
                    "source_file": pdf_path,
                    "rag_chunks": rag_chunks,
                    "extracted_tables": advanced_result["tables"],
                    "extracted_images": advanced_result["images"],
                    "processing_info": {
                        "total_elements": len(elements),
                        "text_elements": len(text_elements),
                        "connected_blocks": len(connected_blocks),
                        "processing_time": time.time() - start_time,
                        "method": "Enhanced (Unstructured + Table Transformer)"
                    }
                }
                metadata_path = output_path / "enhanced_metadata.json"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
                print(f"   ✅ 기본 메타데이터 저장: {metadata_path}")
            
            # 8단계: 키워드 추출 및 추가
            self.logger.info("8단계: 키워드 추출 및 추가")
            print("🔍 키워드 추출 중...")
            
            try:
                # KeyBERT 기반 키워드 추출기 사용
                from keyword_extractor import KeywordExtractor
                
                # 키워드 추출기 초기화
                keyword_extractor = KeywordExtractor()
                
                # 문서 제목 추출
                def extract_document_title(chunks):
                    """문서 제목 추출"""
                    if chunks and len(chunks) > 0:
                        first_chunk = chunks[0]
                        if 'metadata' in first_chunk and 'heading' in first_chunk['metadata']:
                            heading = first_chunk['metadata']['heading']
                            if heading and len(heading.strip()) > 0:
                                return heading.strip()
                    return "의료기기 가이드라인"
                
                # 문서 제목 추출
                document_title = extract_document_title(user_schema_json if 'user_schema_json' in locals() else rag_chunks)
                print(f"📋 문서 제목: {document_title}")
                
                # 키워드 개수 설정 (기본값: 5개)
                keyword_count = 5
                
                # 사용자 스키마 JSON에 키워드 추가
                if 'user_schema_json' in locals():
                    print("📋 사용자 스키마 JSON에 키워드 추가 중...")
                    
                    # 각 청크에 키워드 추가
                    for chunk in user_schema_json:
                        if 'text' in chunk:
                            keywords = keyword_extractor.extract_keywords_with_title_similarity(
                                chunk['text'], document_title, top_k=keyword_count
                            )
                            chunk['keywords'] = keywords
                    
                    # 키워드가 추가된 사용자 스키마 JSON 저장
                    user_schema_with_keywords_path = output_path / "user_schema_with_keywords.json"
                    with open(user_schema_with_keywords_path, 'w', encoding='utf-8') as f:
                        json.dump(user_schema_json, f, ensure_ascii=False, indent=2, default=str)
                    print(f"   ✅ 키워드가 추가된 사용자 스키마 JSON 저장: {user_schema_with_keywords_path}")
                
                # RAG 청크에도 키워드 추가
                print("📊 RAG 청크에 키워드 추가 중...")
                for chunk in rag_chunks:
                    if 'text' in chunk:
                        keywords = keyword_extractor.extract_keywords_with_title_similarity(
                            chunk['text'], document_title, top_k=keyword_count
                        )
                        chunk['keywords'] = keywords
                
                # 키워드가 추가된 RAG 청크 저장
                rag_chunks_with_keywords_path = output_path / "rag_chunks_with_keywords.json"
                with open(rag_chunks_with_keywords_path, 'w', encoding='utf-8') as f:
                    json.dump(rag_chunks, f, ensure_ascii=False, indent=2, default=str)
                print(f"   ✅ 키워드가 추가된 RAG 청크 저장: {rag_chunks_with_keywords_path}")
                
                # 메인 metadata.json 파일에 키워드가 추가된 사용자 스키마 JSON 저장
                if 'user_schema_json' in locals():
                    print("📋 메인 metadata.json 파일에 키워드 추가 중...")
                    metadata_path = output_path / "metadata.json"
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(user_schema_json, f, ensure_ascii=False, indent=2, default=str)
                    print(f"   ✅ 키워드가 포함된 메인 metadata.json 저장: {metadata_path}")
                
            except ImportError:
                self.logger.warning("키워드 추출기를 찾을 수 없습니다.")
                print("   ⚠️ 키워드 추출 실패")
            except Exception as e:
                self.logger.error(f"키워드 추출 중 오류 발생: {e}")
                print(f"   ❌ 키워드 추출 오류: {e}")
            
            # 9단계: 최종 요약 생성
            self.logger.info("9단계: 최종 요약 생성")
            print("📊 최종 요약 생성 중...")
            summary = self.create_enhanced_summary(
                connected_blocks, 
                advanced_result["tables"], 
                advanced_result["images"], 
                rag_chunks
            )
            summary_path = output_path / "enhanced_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            print(f"   ✅ 요약 저장: {summary_path}")
            
            processing_time = time.time() - start_time
            print(f"🎉 향상된 PDF 처리 완료! (소요시간: {processing_time:.2f}초)")
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

class EnhancedBatchProcessor:
    """향상된 배치 처리기"""
    
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
            processor = EnhancedPDFProcessor(use_gpu=self.use_gpu)
            
            summary = processor.process_pdf_enhanced(
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
                f"텍스트 블록: {summary.get('text_blocks_count', 0)}, "
                f"테이블: {summary.get('table_statistics', {}).get('total_tables', 0)}, "
                f"이미지: {summary.get('image_statistics', {}).get('total_images', 0)}",
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
        batch_summary_path = self.output_dir / "enhanced_batch_summary.json"
        with open(batch_summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        
        self._print_detailed_statistics(summary)
        return summary
    
    def _print_detailed_statistics(self, summary: Dict[str, Any]):
        """상세 통계 출력"""
        self.logger.info("=" * 80)
        self.logger.info("향상된 PDF 파싱 결과 요약")
        self.logger.info("=" * 80)
        self.logger.info(f"총 파일 수: {summary['total_files']}")
        self.logger.info(f"성공한 파일 수: {summary['successful_files']}")
        self.logger.info(f"실패한 파일 수: {summary['failed_files']}")
        self.logger.info(f"성공률: {summary['success_rate']:.2%}")
        self.logger.info(f"총 처리 시간: {summary['total_processing_time']:.2f}초")
        self.logger.info(f"평균 처리 시간: {summary['average_processing_time']:.2f}초")
        
        # 성공한 파일들의 상세 통계
        if summary['successful_files'] > 0:
            successful_results = [r for r in summary['results'] if r['status'] == 'success']
            
            total_text_blocks = sum(r['summary'].get('text_blocks_count', 0) for r in successful_results)
            total_tables = sum(r['summary'].get('table_statistics', {}).get('total_tables', 0) for r in successful_results)
            total_images = sum(r['summary'].get('image_statistics', {}).get('total_images', 0) for r in successful_results)
            
            self.logger.info(f"총 추출된 텍스트 블록: {total_text_blocks}")
            self.logger.info(f"총 추출된 테이블: {total_tables}")
            self.logger.info(f"총 추출된 이미지: {total_images}")
        
        self.logger.info("=" * 80)

if __name__ == "__main__":
    # 사용 예시
    processor = EnhancedBatchProcessor(use_gpu=False)
    summary = processor.process_all_pdfs()
    print("처리 완료!") 