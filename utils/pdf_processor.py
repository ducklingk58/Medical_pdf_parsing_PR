import os
import re
import json
import pandas as pd
import io
from pathlib import Path
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
from unstructured.partition.auto import partition
from unstructured.documents.elements import Table, Title, NarrativeText, Image
import logging
from config.settings import Settings

class PDFProcessor:
    """Unstructured를 활용한 고급 PDF 처리기"""
    
    def __init__(self, similarity_threshold: float = None):
        self.similarity_threshold = similarity_threshold or Settings.SIMILARITY_THRESHOLD
        self.sentence_model = SentenceTransformer(Settings.SENTENCE_MODEL)
        self.logger = logging.getLogger(__name__)
        
    def partition_pdf(self, pdf_path: str) -> List:
        """Unstructured를 사용한 PDF 초기 파싱"""
        try:
            self.logger.info(f"PDF 파싱 시작: {pdf_path}")
            elements = partition(
                filename=pdf_path,
                include_image_metadata=Settings.INCLUDE_IMAGE_METADATA,
                extract_tables=Settings.PDF_EXTRACT_TABLES,
                pdf_extract_images=Settings.PDF_EXTRACT_IMAGES,
                strategy="fast"
            )
            self.logger.info(f"PDF 파싱 완료: {len(elements)}개 요소 추출")
            return elements
        except Exception as e:
            self.logger.error(f"PDF 파싱 오류: {str(e)}")
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
    
    def extract_tables(self, elements: List) -> List[Dict[str, Any]]:
        """표 데이터 추출 및 구조화"""
        tables = []
        
        for i, element in enumerate(elements):
            if isinstance(element, Table):
                self.logger.debug(f"표 {i+1} 추출 중...")
                
                table_data = {
                    "id": f"table_{i+1:03d}",
                    "type": "table",
                    "text": element.text,
                    "metadata": element.metadata.dict() if hasattr(element, 'metadata') else {}
                }
                
                # CSV 형태로 구조화 (pandas DataFrame으로 변환)
                if hasattr(element.metadata, 'text_as_csv') and element.metadata.text_as_csv:
                    try:
                        df = pd.read_csv(io.StringIO(element.metadata.text_as_csv))
                        table_data["structured_data"] = df.to_dict('records')
                        table_data["columns"] = df.columns.tolist()
                        table_data["shape"] = df.shape
                        table_data["dataframe"] = df
                        self.logger.debug(f"표 {i+1} CSV 변환 성공: {df.shape}")
                    except Exception as e:
                        self.logger.warning(f"표 {i+1} CSV 변환 오류: {str(e)}")
                
                # HTML 형태도 저장
                if hasattr(element.metadata, 'text_as_html') and element.metadata.text_as_html:
                    table_data["html"] = element.metadata.text_as_html
                
                tables.append(table_data)
        
        self.logger.info(f"총 {len(tables)}개 표 추출 완료")
        return tables
    
    def extract_images(self, elements: List) -> List[Dict[str, Any]]:
        """이미지 데이터 추출"""
        images = []
        
        for i, element in enumerate(elements):
            if isinstance(element, Image):
                self.logger.debug(f"이미지 {i+1} 추출 중...")
                
                image_data = {
                    "id": f"image_{i+1:03d}",
                    "type": "image",
                    "text": element.text,  # 이미지 캡션
                    "metadata": element.metadata.dict() if hasattr(element, 'metadata') else {}
                }
                
                # 이미지 파일 경로가 있다면 저장
                if hasattr(element.metadata, 'image_path') and element.metadata.image_path:
                    image_data["image_path"] = element.metadata.image_path
                
                # 페이지 정보 추가
                if hasattr(element.metadata, 'page_number'):
                    image_data["page_number"] = element.metadata.page_number
                
                images.append(image_data)
        
        self.logger.info(f"총 {len(images)}개 이미지 추출 완료")
        return images
    
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
        
        # 특수 키워드 확인
        break_keywords = ['목차', '서론', '결론', '참고문헌', '부록', 'Abstract', 'Introduction', 'Conclusion']
        if any(keyword in text2 for keyword in break_keywords):
            return True
        
        # 문단 시작 패턴 (소문자로 시작하는 경우)
        if text2.strip() and text2.strip()[0].islower():
            return True
        
        return False
    
    def create_rag_chunks(self, text_blocks: List[str], chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """RAG 친화적 텍스트 청킹"""
        chunk_size = chunk_size or Settings.CHUNK_SIZE
        overlap = overlap or Settings.CHUNK_OVERLAP
        
        chunks = []
        
        for block_idx, block in enumerate(text_blocks):
            words = block.split()
            
            for i in range(0, len(words), chunk_size - overlap):
                chunk_words = words[i:i + chunk_size]
                chunk_text = ' '.join(chunk_words)
                
                if chunk_text.strip():
                    chunks.append({
                        "id": f"chunk_{len(chunks):06d}",
                        "text": chunk_text,
                        "block_index": block_idx,
                        "chunk_index": len(chunks),
                        "word_count": len(chunk_words),
                        "token_estimate": len(chunk_words) * 1.3  # 대략적인 토큰 수 추정
                    })
        
        self.logger.info(f"RAG 청킹 완료: {len(chunks)}개 청크 생성")
        return chunks
    
    def save_tables(self, tables: List[Dict], output_dir: Path) -> List[str]:
        """표 데이터를 파일로 저장"""
        table_files = []
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        for table in tables:
            table_id = table["id"]
            
            # JSON 형태로 저장
            json_path = tables_dir / f"{table_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2)
            
            # CSV 형태로도 저장 (구조화된 데이터가 있는 경우)
            if "dataframe" in table:
                csv_path = tables_dir / f"{table_id}.csv"
                table["dataframe"].to_csv(csv_path, index=False, encoding='utf-8-sig')
            
            table_files.append(str(json_path))
        
        self.logger.info(f"표 데이터 저장 완료: {len(table_files)}개 파일")
        return table_files
    
    def save_images(self, images: List[Dict], output_dir: Path) -> List[str]:
        """이미지 메타데이터 저장"""
        image_files = []
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        for image in images:
            image_id = image["id"]
            json_path = images_dir / f"{image_id}.json"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(image, f, ensure_ascii=False, indent=2)
            
            image_files.append(str(json_path))
        
        self.logger.info(f"이미지 메타데이터 저장 완료: {len(image_files)}개 파일")
        return image_files
    
    def create_markdown(self, text_blocks: List[str], table_files: List[str], 
                       image_files: List[str], output_dir: Path) -> str:
        """최종 마크다운 파일 생성"""
        md_content = []
        
        # 텍스트 블록 추가
        for i, block in enumerate(text_blocks):
            md_content.append(f"## 텍스트 블록 {i+1}\n")
            md_content.append(block)
            md_content.append("\n\n")
        
        # 표 참조 추가
        if table_files:
            md_content.append("## 추출된 표\n")
            for table_file in table_files:
                table_name = Path(table_file).stem
                md_content.append(f"- [표 데이터: {table_name}]({table_file})\n")
            md_content.append("\n")
        
        # 이미지 참조 추가
        if image_files:
            md_content.append("## 추출된 이미지\n")
            for image_file in image_files:
                image_name = Path(image_file).stem
                md_content.append(f"- [이미지 메타데이터: {image_name}]({image_file})\n")
            md_content.append("\n")
        
        md_path = output_dir / "final_markdown.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(''.join(md_content))
        
        self.logger.info(f"마크다운 파일 생성 완료: {md_path}")
        return str(md_path)
    
    def create_summary(self, text_blocks: List[str], tables: List[Dict], 
                      images: List[Dict], chunks: List[Dict]) -> Dict[str, Any]:
        """파싱 결과 요약 생성"""
        total_words = sum(len(block.split()) for block in text_blocks)
        total_tokens = sum(chunk.get("token_estimate", 0) for chunk in chunks)
        
        summary = {
            "text_blocks_count": len(text_blocks),
            "tables_count": len(tables),
            "images_count": len(images),
            "rag_chunks_count": len(chunks),
            "total_words": total_words,
            "total_tokens_estimate": total_tokens,
            "processing_timestamp": pd.Timestamp.now().isoformat(),
            "settings": {
                "similarity_threshold": self.similarity_threshold,
                "chunk_size": Settings.CHUNK_SIZE,
                "chunk_overlap": Settings.CHUNK_OVERLAP
            }
        }
        
        return summary
    
    def process_pdf(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """단일 PDF 파일 전체 처리"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"PDF 처리 시작: {pdf_path}")
        
        try:
            # 1. 초기 파싱
            elements = self.partition_pdf(pdf_path)
            
            # 2. 데이터 분류 및 추출
            text_elements = self.extract_text_elements(elements)
            tables = self.extract_tables(elements)
            images = self.extract_images(elements)
            
            # 3. 텍스트 재구성 및 문장 연결
            connected_blocks = self.connect_sentences(text_elements)
            
            # 4. RAG 친화적 청킹
            rag_chunks = self.create_rag_chunks(connected_blocks)
            
            # 5. 파일 저장
            table_files = self.save_tables(tables, output_path)
            image_files = self.save_images(images, output_path)
            md_file = self.create_markdown(connected_blocks, table_files, image_files, output_path)
            
            # 6. 메타데이터 저장
            metadata = {
                "source_file": pdf_path,
                "text_blocks": connected_blocks,
                "rag_chunks": rag_chunks,
                "tables": tables,
                "images": images,
                "processing_info": {
                    "total_elements": len(elements),
                    "text_elements": len(text_elements),
                    "connected_blocks": len(connected_blocks)
                }
            }
            
            metadata_path = output_path / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 7. 요약 생성
            summary = self.create_summary(connected_blocks, tables, images, rag_chunks)
            summary_path = output_path / "summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"PDF 처리 완료: {pdf_path}")
            return summary
            
        except Exception as e:
            self.logger.error(f"PDF 처리 중 오류 발생: {pdf_path} - {str(e)}")
            raise 