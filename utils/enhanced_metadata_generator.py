"""
향상된 메타데이터 생성기
제공된 JSON 템플릿에 맞는 메타데이터 생성
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

class EnhancedMetadataGenerator:
    """향상된 메타데이터 생성기 - 제공된 JSON 템플릿 준수"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_chunk_metadata(self, 
                               chunk_id: str,
                               original_file_name: str,
                               page_numbers: List[int],
                               category: str,
                               text_content: str,
                               section_title: Optional[str] = None,
                               table_references: Optional[List[str]] = None,
                               image_references: Optional[List[str]] = None) -> Dict[str, Any]:
        """청크 메타데이터 생성"""
        
        metadata = {
            "chunk_id": chunk_id,
            "original_file_name": original_file_name,
            "page_numbers": page_numbers,
            "category": category,
            "text_content": text_content,
            "section_title": section_title,
            "table_references": table_references or [],
            "image_references": image_references or [],
            "source_type": "PDF",
            "extraction_tool": "Unstructured_LayoutParser_PaddleOCR"
        }
        
        return metadata
    
    def create_text_chunk_metadata(self, 
                                  chunk_id: str,
                                  original_file_name: str,
                                  text_content: str,
                                  page_numbers: List[int],
                                  section_title: Optional[str] = None,
                                  table_refs: Optional[List[str]] = None,
                                  image_refs: Optional[List[str]] = None) -> Dict[str, Any]:
        """텍스트 청크 메타데이터 생성"""
        
        return self.generate_chunk_metadata(
            chunk_id=chunk_id,
            original_file_name=original_file_name,
            page_numbers=page_numbers,
            category="NarrativeText",
            text_content=text_content,
            section_title=section_title,
            table_references=table_refs,
            image_references=image_refs
        )
    
    def create_title_chunk_metadata(self, 
                                   chunk_id: str,
                                   original_file_name: str,
                                   text_content: str,
                                   page_numbers: List[int]) -> Dict[str, Any]:
        """제목 청크 메타데이터 생성"""
        
        return self.generate_chunk_metadata(
            chunk_id=chunk_id,
            original_file_name=original_file_name,
            page_numbers=page_numbers,
            category="Title",
            text_content=text_content,
            section_title=None,
            table_references=[],
            image_references=[]
        )
    
    def create_table_reference_metadata(self, 
                                       chunk_id: str,
                                       original_file_name: str,
                                       table_file_path: str,
                                       page_numbers: List[int],
                                       table_caption: str) -> Dict[str, Any]:
        """테이블 참조 메타데이터 생성"""
        
        return self.generate_chunk_metadata(
            chunk_id=chunk_id,
            original_file_name=original_file_name,
            page_numbers=page_numbers,
            category="TableRef",
            text_content=f"테이블 참조: {table_caption}",
            section_title=None,
            table_references=[table_file_path],
            image_references=[]
        )
    
    def create_image_reference_metadata(self, 
                                       chunk_id: str,
                                       original_file_name: str,
                                       image_file_path: str,
                                       page_numbers: List[int],
                                       image_caption: str) -> Dict[str, Any]:
        """이미지 참조 메타데이터 생성"""
        
        return self.generate_chunk_metadata(
            chunk_id=chunk_id,
            original_file_name=original_file_name,
            page_numbers=page_numbers,
            category="ImageRef",
            text_content=f"이미지 참조: {image_caption}",
            section_title=None,
            table_references=[],
            image_references=[image_file_path]
        )
    
    def generate_document_metadata(self, 
                                  original_file_name: str,
                                  text_chunks: List[Dict[str, Any]],
                                  table_files: List[str],
                                  image_files: List[str],
                                  processing_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """문서 전체 메타데이터 생성"""
        
        metadata_list = []
        
        # 텍스트 청크 메타데이터 추가
        for chunk in text_chunks:
            metadata_list.append(chunk)
        
        # 테이블 참조 메타데이터 추가
        for i, table_file in enumerate(table_files):
            table_id = f"{Path(original_file_name).stem}_table_{i+1:03d}"
            table_caption = f"테이블 {i+1}"
            
            # 테이블 파일에서 페이지 번호 추출 (파일명에서)
            page_numbers = self._extract_page_numbers_from_filename(table_file)
            
            table_metadata = self.create_table_reference_metadata(
                chunk_id=f"{Path(original_file_name).stem}_table_ref_{i+1:03d}",
                original_file_name=original_file_name,
                table_file_path=table_file,
                page_numbers=page_numbers,
                table_caption=table_caption
            )
            metadata_list.append(table_metadata)
        
        # 이미지 참조 메타데이터 추가
        for i, image_file in enumerate(image_files):
            image_id = f"{Path(original_file_name).stem}_image_{i+1:03d}"
            image_caption = f"이미지 {i+1}"
            
            # 이미지 파일에서 페이지 번호 추출 (파일명에서)
            page_numbers = self._extract_page_numbers_from_filename(image_file)
            
            image_metadata = self.create_image_reference_metadata(
                chunk_id=f"{Path(original_file_name).stem}_image_ref_{i+1:03d}",
                original_file_name=original_file_name,
                image_file_path=image_file,
                page_numbers=page_numbers,
                image_caption=image_caption
            )
            metadata_list.append(image_metadata)
        
        return metadata_list
    
    def _extract_page_numbers_from_filename(self, filename: str) -> List[int]:
        """파일명에서 페이지 번호 추출"""
        # 파일명에서 페이지 번호 패턴 찾기
        page_pattern = r'page_(\d+)'
        matches = re.findall(page_pattern, filename)
        
        if matches:
            return [int(match) for match in matches]
        else:
            # 페이지 번호가 없으면 기본값 1 반환
            return [1]
    
    def save_metadata(self, metadata_list: List[Dict[str, Any]], output_path: Path):
        """메타데이터를 JSON 파일로 저장"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_list, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"메타데이터 저장 완료: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"메타데이터 저장 실패: {str(e)}")
            return False
    
    def create_summary_metadata(self, 
                               original_file_name: str,
                               text_chunks_count: int,
                               table_files_count: int,
                               image_files_count: int,
                               total_pages: int,
                               processing_time: float) -> Dict[str, Any]:
        """요약 메타데이터 생성"""
        
        return {
            "original_file_name": original_file_name,
            "processing_timestamp": datetime.now().isoformat(),
            "extraction_tool": "Unstructured_LayoutParser_PaddleOCR",
            "statistics": {
                "total_pages": total_pages,
                "text_chunks_count": text_chunks_count,
                "table_files_count": table_files_count,
                "image_files_count": image_files_count,
                "total_elements": text_chunks_count + table_files_count + image_files_count
            },
            "processing_info": {
                "processing_time_seconds": processing_time,
                "processing_method": "Enhanced (Unstructured + LayoutParser + PaddleOCR)",
                "output_formats": ["JSON", "CSV", "Excel", "HTML", "PNG", "Markdown"]
            }
        } 