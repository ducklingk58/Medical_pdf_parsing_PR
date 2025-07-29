#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
사용자 정의 스키마 JSON 생성기
사용자가 제공한 배열 형태의 JSON 스키마에 맞춰 PDF 처리 결과 생성
"""

import json
import uuid
import re
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
from datetime import datetime

class UserSchemaJSONGenerator:
    """사용자 정의 배열 스키마에 맞는 JSON 생성기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_user_schema_json(self, 
                                 text_chunks: List[Dict[str, Any]], 
                                 extracted_tables: List[Dict[str, Any]],
                                 source_file: str) -> List[Dict[str, Any]]:
        """
        사용자 정의 스키마에 맞는 JSON 배열 생성
        
        스키마:
        [
          {
            "id": "string",
            "text": "string",
            "metadata": {
              "page": "integer",
              "type": "string", 
              "document_order": "integer",
              "content_length": "integer",
              "has_table": "boolean",
              "section_title": "string",
              "preprocessed": "boolean"
            }
          }
        ]
        """
        try:
            self.logger.info(f"사용자 스키마 JSON 생성 시작: {source_file}")
            
            result_array = []
            document_order = 1
            current_section_title = "문서 시작"
            
            # 1. 텍스트 청크 처리
            for chunk in text_chunks:
                chunk_item = self._create_text_chunk_item(
                    chunk, document_order, current_section_title
                )
                if chunk_item:
                    result_array.append(chunk_item)
                    document_order += 1
                    
                    # 섹션 제목 업데이트
                    if self._is_section_title(chunk):
                        current_section_title = chunk.get('content', chunk.get('text', ''))[:100]
            
            # 2. 표 데이터 처리 (텍스트로 변환하여 추가)
            for table in extracted_tables:
                table_item = self._create_table_chunk_item(
                    table, document_order, current_section_title
                )
                if table_item:
                    result_array.append(table_item)
                    document_order += 1
            
            self.logger.info(f"사용자 스키마 JSON 생성 완료: {len(result_array)}개 아이템")
            return result_array
            
        except Exception as e:
            self.logger.error(f"사용자 스키마 JSON 생성 실패: {str(e)}")
            return self._create_fallback_array(source_file)
    
    def _create_text_chunk_item(self, chunk: Dict[str, Any], document_order: int, 
                               section_title: str) -> Optional[Dict[str, Any]]:
        """텍스트 청크를 사용자 스키마 아이템으로 변환"""
        
        try:
            # 텍스트 내용 추출
            text_content = chunk.get('content', chunk.get('text', '')).strip()
            if not text_content or len(text_content) < 10:
                return None
            
            # 페이지 번호 추출
            page_number = chunk.get('page_number', chunk.get('page', 1))
            if isinstance(page_number, str):
                try:
                    page_number = int(re.findall(r'\d+', page_number)[0])
                except:
                    page_number = 1
            
            # 청크 타입 결정
            chunk_type = self._determine_chunk_type(chunk)
            
            # 표 포함 여부 확인
            has_table = self._check_has_table(text_content)
            
            # 전처리 여부 (기본적으로 모든 청크가 전처리됨)
            preprocessed = True
            
            # 고유 ID 생성
            chunk_id = str(uuid.uuid4())
            
            return {
                "id": chunk_id,
                "text": text_content,
                "metadata": {
                    "page": int(page_number),
                    "type": chunk_type,
                    "document_order": document_order,
                    "content_length": len(text_content),
                    "has_table": has_table,
                    "section_title": section_title,
                    "preprocessed": preprocessed
                }
            }
            
        except Exception as e:
            self.logger.warning(f"텍스트 청크 변환 실패: {str(e)}")
            return None
    
    def _create_table_chunk_item(self, table: Dict[str, Any], document_order: int,
                                section_title: str) -> Optional[Dict[str, Any]]:
        """표 데이터를 사용자 스키마 아이템으로 변환"""
        
        try:
            # 표를 텍스트로 변환
            table_text = self._convert_table_to_text(table)
            if not table_text or len(table_text) < 10:
                return None
            
            # 페이지 번호 추출
            page_number = table.get('page_number', table.get('page', 1))
            if isinstance(page_number, str):
                try:
                    page_number = int(re.findall(r'\d+', page_number)[0])
                except:
                    page_number = 1
            
            # 고유 ID 생성
            table_id = str(uuid.uuid4())
            
            return {
                "id": table_id,
                "text": table_text,
                "metadata": {
                    "page": int(page_number),
                    "type": "table",
                    "document_order": document_order,
                    "content_length": len(table_text),
                    "has_table": True,
                    "section_title": section_title,
                    "preprocessed": True
                }
            }
            
        except Exception as e:
            self.logger.warning(f"표 청크 변환 실패: {str(e)}")
            return None
    
    def _determine_chunk_type(self, chunk: Dict[str, Any]) -> str:
        """청크 타입 결정"""
        
        # 기존 category나 type 확인
        category = chunk.get('category', '').lower()
        chunk_type = chunk.get('type', '').lower()
        subtype = chunk.get('subtype', '').lower()
        
        # 내용 분석
        content = chunk.get('content', chunk.get('text', '')).lower()
        
        # 타입 결정 로직
        if category == 'title' or subtype == 'title' or chunk_type == 'title':
            return "title"
        elif category == 'narrativetext' or 'paragraph' in chunk_type:
            return "paragraph"
        elif category == 'table' or chunk_type == 'table':
            return "table"
        elif 'list' in category or 'list' in chunk_type:
            return "list"
        elif len(content) < 50 and any(keyword in content for keyword in ['개요', '목적', '범위', '지침']):
            return "heading"
        elif self._is_section_title(chunk):
            return "section_title"
        else:
            return "text"
    
    def _is_section_title(self, chunk: Dict[str, Any]) -> bool:
        """섹션 제목인지 판별"""
        
        content = chunk.get('content', chunk.get('text', '')).strip()
        category = chunk.get('category', '').lower()
        
        # 길이 기반 판별
        if len(content) > 100:
            return False
        
        # 카테고리 기반 판별
        if category == 'title':
            return True
        
        # 패턴 기반 판별
        if re.match(r'^[0-9]+\.\s*[가-힣]', content):  # "1. 개요" 형태
            return True
        
        if re.match(r'^[①-⑳]\s*[가-힣]', content):  # "① 목적" 형태
            return True
        
        if re.match(r'^[가-다]\.\s*[가-힣]', content):  # "가. 일반사항" 형태
            return True
        
        # 키워드 기반 판별
        if any(keyword in content for keyword in ['개요', '목적', '적용범위', '용어정의', '일반사항']):
            return True
        
        return False
    
    def _check_has_table(self, text: str) -> bool:
        """텍스트에 표 관련 내용이 포함되어 있는지 확인"""
        
        table_indicators = [
            '표', 'table', '항목', '구분', '기준', '수치', 
            '|', '┌', '┐', '└', '┘', '─', '│'
        ]
        
        return any(indicator in text for indicator in table_indicators)
    
    def _convert_table_to_text(self, table: Dict[str, Any]) -> str:
        """표 데이터를 텍스트로 변환"""
        
        try:
            # 표 제목 추출
            title = table.get('caption', '')
            if not title:
                title = f"표 (페이지 {table.get('page_number', 1)})"
            
            text_parts = [title] if title else []
            
            # 표 데이터 변환
            table_data = table.get('table_data', [])
            if table_data and isinstance(table_data, list):
                for row in table_data:
                    if isinstance(row, list):
                        row_text = " | ".join(str(cell).strip() for cell in row if str(cell).strip())
                        if row_text:
                            text_parts.append(row_text)
            
            # cell_texts에서 데이터 추출
            if not text_parts and table.get('cell_texts'):
                cell_texts = table['cell_texts']
                if isinstance(cell_texts, list):
                    for cell in cell_texts:
                        cell_text = cell.get('text', '').strip()
                        if cell_text:
                            text_parts.append(cell_text)
            
            # extracted_text 사용
            if not text_parts and table.get('extracted_text'):
                text_parts.append(table['extracted_text'])
            
            return "\n".join(text_parts) if text_parts else ""
            
        except Exception as e:
            self.logger.warning(f"표 텍스트 변환 실패: {str(e)}")
            return f"표 데이터 (페이지 {table.get('page_number', 1)})"
    
    def _create_fallback_array(self, source_file: str) -> List[Dict[str, Any]]:
        """오류 시 기본 배열 생성"""
        
        fallback_id = str(uuid.uuid4())
        
        return [{
            "id": fallback_id,
            "text": f"PDF 파일 '{Path(source_file).name}' 처리 중 오류가 발생했습니다.",
            "metadata": {
                "page": 1,
                "type": "error",
                "document_order": 1,
                "content_length": 50,
                "has_table": False,
                "section_title": "오류",
                "preprocessed": False
            }
        }]

def create_user_schema_json(text_chunks: List[Dict[str, Any]], 
                           extracted_tables: List[Dict[str, Any]], 
                           source_file: str) -> List[Dict[str, Any]]:
    """사용자 스키마 JSON 생성 편의 함수"""
    
    generator = UserSchemaJSONGenerator()
    return generator.generate_user_schema_json(text_chunks, extracted_tables, source_file) 