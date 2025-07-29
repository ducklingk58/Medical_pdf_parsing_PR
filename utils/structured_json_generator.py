#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
구조화된 JSON 생성기
사용자 제공 스키마에 맞는 문서 구조 생성
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path

class StructuredJSONGenerator:
    """사용자 정의 스키마에 맞는 구조화된 JSON 생성기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_structured_document(self, 
                                   text_chunks: List[Dict[str, Any]], 
                                   extracted_tables: List[Dict[str, Any]],
                                   source_file: str) -> Dict[str, Any]:
        """텍스트 청크와 표 데이터로부터 구조화된 문서 생성"""
        
        try:
            # 1. 문서 메타데이터 추출
            document_metadata = self._extract_document_metadata(text_chunks, source_file)
            
            # 2. 섹션 구조 생성
            sections = self._create_sections_from_chunks(text_chunks)
            
            # 3. 표 구조화
            structured_tables = self._structure_tables(extracted_tables)
            
            # 4. 최종 구조화된 JSON 생성
            structured_document = {
                "document_title": document_metadata["title"],
                "version": document_metadata.get("version", "N/A"),
                "summary": document_metadata["summary"],
                "sections": sections,
                "tables": structured_tables,
                "metadata": {
                    "source_file": source_file,
                    "processing_date": document_metadata["processing_date"],
                    "total_sections": len(sections),
                    "total_tables": len(structured_tables),
                    "document_type": self._determine_document_type(text_chunks)
                }
            }
            
            # text_blocks는 완전히 제외됨
            self.logger.info(f"구조화된 문서 생성 완료: {len(sections)}개 섹션, {len(structured_tables)}개 표")
            
            return structured_document
            
        except Exception as e:
            self.logger.error(f"구조화된 JSON 생성 실패: {str(e)}")
            return self._create_fallback_structure(source_file)
    
    def _extract_document_metadata(self, text_chunks: List[Dict[str, Any]], source_file: str) -> Dict[str, Any]:
        """문서 메타데이터 추출"""
        
        # 제목 추출 (첫 번째 title 타입 청크 또는 가장 큰 폰트)
        title = "문서 제목"
        version = "N/A"
        
        title_candidates = []
        
        for chunk in text_chunks[:10]:  # 첫 10개 청크에서 제목 찾기
            content = chunk.get('content', chunk.get('text', ''))
            
            # 제목 타입이거나 짧고 의미있는 텍스트
            if (chunk.get('category') == 'Title' or 
                chunk.get('subtype') == 'title' or
                (len(content) < 100 and any(keyword in content for keyword in ['지침', '가이드', '규정', '기준']))):
                title_candidates.append(content.strip())
        
        if title_candidates:
            title = title_candidates[0]
        
        # 버전 정보 추출
        for chunk in text_chunks[:20]:
            content = chunk.get('content', chunk.get('text', ''))
            version_match = re.search(r'(\d{4}\.\d{2}|\d{4}-\d{2}|v\d+\.\d+|버전\s*\d+)', content)
            if version_match:
                version = version_match.group(1)
                break
        
        # 요약 생성 (처음 몇 개 paragraph에서)
        summary_parts = []
        for chunk in text_chunks[:5]:
            content = chunk.get('content', chunk.get('text', ''))
            if (chunk.get('category') == 'NarrativeText' and 
                len(content) > 20 and 
                any(keyword in content for keyword in ['목적', '지침', '규정', '안전성', '의약품'])):
                summary_parts.append(content.strip())
                if len(' '.join(summary_parts)) > 200:
                    break
        
        summary = ' '.join(summary_parts)[:300] + "..." if summary_parts else "이 문서는 의약품 관련 지침서입니다."
        
        return {
            "title": title,
            "version": version,
            "summary": summary,
            "processing_date": "2025-01-24"  # 현재 날짜
        }
    
    def _create_sections_from_chunks(self, text_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """텍스트 청크로부터 섹션 구조 생성"""
        
        sections = []
        current_section = None
        current_subsection = None
        
        for chunk in text_chunks:
            content = chunk.get('content', chunk.get('text', '')).strip()
            category = chunk.get('category', '')
            chunk_type = chunk.get('type', 'text')  # 청크 타입 확인
            
            if not content:
                continue
            
            # 섹션 제목 판별 (짧고 구조적인 텍스트)
            is_main_section = (
                category == 'Title' or 
                chunk.get('subtype') == 'title' or
                (len(content) < 50 and 
                 any(keyword in content for keyword in ['개요', '적용', '범위', '지침', '검토', '보고', '작성', '예시']))
            )
            
            # 하위 섹션 판별
            is_subsection = (
                len(content) < 100 and
                (content.startswith(('1.', '2.', '3.', '①', '②', '③', '가.', '나.', '다.')) or
                 any(keyword in content for keyword in ['목적', '관련', '일반', '결과', '조치']))
            )
            
            if is_main_section and len(content) < 50:
                # 새로운 메인 섹션 시작
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "title": content,
                    "type": chunk_type,  # 섹션 제목의 타입 추가
                    "subsections": []
                }
                current_subsection = None
                
            elif is_subsection and current_section:
                # 새로운 하위 섹션 시작
                current_subsection = {
                    "title": content,
                    "type": chunk_type,  # 하위 섹션 제목의 타입 추가
                    "content": ""
                }
                current_section["subsections"].append(current_subsection)
                
            elif current_subsection and len(content) > 20:
                # 현재 하위 섹션에 내용 추가
                if current_subsection["content"]:
                    current_subsection["content"] += " " + content
                else:
                    current_subsection["content"] = content
                # 내용의 타입도 추가 (기존 타입과 새로운 타입을 병합)
                if "content_types" not in current_subsection:
                    current_subsection["content_types"] = []
                if chunk_type not in current_subsection["content_types"]:
                    current_subsection["content_types"].append(chunk_type)
                    
            elif current_section and len(content) > 20:
                # 하위 섹션 없이 메인 섹션에 직접 내용 추가
                if not current_section.get("content"):
                    current_section["content"] = content
                else:
                    current_section["content"] += " " + content
                # 내용의 타입도 추가
                if "content_types" not in current_section:
                    current_section["content_types"] = []
                if chunk_type not in current_section["content_types"]:
                    current_section["content_types"].append(chunk_type)
        
        # 마지막 섹션 추가
        if current_section:
            sections.append(current_section)
        
        # 빈 섹션 정리
        cleaned_sections = []
        for section in sections:
            if section.get("subsections"):
                # 빈 하위 섹션 제거
                section["subsections"] = [
                    sub for sub in section["subsections"] 
                    if sub.get("content", "").strip()
                ]
            
            # 내용이 있는 섹션만 유지
            if (section.get("content", "").strip() or 
                section.get("subsections")):
                cleaned_sections.append(section)
        
        return cleaned_sections
    
    def _structure_tables(self, extracted_tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """추출된 표를 구조화된 형태로 변환"""
        
        structured_tables = []
        
        for i, table in enumerate(extracted_tables):
            try:
                # 표 제목 생성
                title = table.get('caption', f'표 {i+1}')
                if not title or title.startswith('표'):
                    # 표 내용에서 제목 추출 시도
                    extracted_text = table.get('extracted_text', '')
                    if extracted_text:
                        first_line = extracted_text.split('\n')[0].strip()
                        if len(first_line) < 100:
                            title = first_line
                
                # 표 데이터 구조화
                table_data = table.get('table_data', [])
                headers = []
                rows = []
                
                if table_data and isinstance(table_data, list):
                    if len(table_data) > 0 and isinstance(table_data[0], list):
                        # 2차원 배열 형태
                        headers = table_data[0] if table_data else []
                        rows = table_data[1:] if len(table_data) > 1 else []
                    else:
                        # 1차원 배열이나 다른 형태
                        headers = ["항목", "내용"]
                        rows = [[str(item)] for item in table_data[:5]]  # 최대 5개만
                
                # cell_texts에서 데이터 추출 시도
                if not headers and table.get('cell_texts'):
                    cell_texts = table['cell_texts']
                    if isinstance(cell_texts, list) and cell_texts:
                        # 행/열 구조 재구성
                        cells_by_row = {}
                        for cell in cell_texts:
                            row = cell.get('row', 0)
                            col = cell.get('col', 0)
                            text = cell.get('text', '').strip()
                            
                            if row not in cells_by_row:
                                cells_by_row[row] = {}
                            cells_by_row[row][col] = text
                        
                        # 헤더와 행 분리
                        if 0 in cells_by_row:
                            headers = [cells_by_row[0].get(i, '') for i in range(max(cells_by_row[0].keys()) + 1)]
                        
                        for row_num in sorted(cells_by_row.keys())[1:]:
                            row_data = [cells_by_row[row_num].get(i, '') for i in range(len(headers))]
                            if any(cell.strip() for cell in row_data):  # 빈 행 제외
                                rows.append(row_data)
                
                # 최소한의 구조라도 생성
                if not headers and not rows:
                    extracted_text = table.get('extracted_text', '')
                    if extracted_text:
                        lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
                        if lines:
                            headers = ["내용"]
                            rows = [[line] for line in lines[:3]]  # 처음 3줄만
                
                structured_table = {
                    "title": title,
                    "type": "table",  # 표는 항상 "table" 타입
                    "headers": headers,
                    "rows": rows,
                    "metadata": {
                        "page_number": table.get('page_number', 1),
                        "extraction_tool": table.get('extraction_tool', 'Unknown'),
                        "confidence_score": table.get('confidence_score', 0.0)
                    }
                }
                
                structured_tables.append(structured_table)
                
            except Exception as e:
                self.logger.warning(f"표 {i+1} 구조화 실패: {str(e)}")
                continue
        
        return structured_tables
    
    def _determine_document_type(self, text_chunks: List[Dict[str, Any]]) -> str:
        """문서 타입 판별"""
        
        content_sample = ""
        for chunk in text_chunks[:10]:
            content_sample += chunk.get('content', chunk.get('text', '')) + " "
        
        content_sample = content_sample.lower()
        
        if any(keyword in content_sample for keyword in ['지침', '가이드라인', 'guideline']):
            return "지침서"
        elif any(keyword in content_sample for keyword in ['규정', '기준', '규칙']):
            return "규정집"
        elif any(keyword in content_sample for keyword in ['보고서', 'report']):
            return "보고서"
        elif any(keyword in content_sample for keyword in ['매뉴얼', 'manual']):
            return "매뉴얼"
        else:
            return "문서"
    
    def _create_fallback_structure(self, source_file: str) -> Dict[str, Any]:
        """오류 시 기본 구조 생성"""
        
        return {
            "document_title": "문서 파싱 결과",
            "version": "N/A",
            "summary": "문서 구조화 중 오류가 발생했습니다.",
            "sections": [],
            "tables": [],
            "metadata": {
                "source_file": source_file,
                "processing_date": "2025-01-24",
                "total_sections": 0,
                "total_tables": 0,
                "document_type": "문서",
                "error": "구조화 실패"
            }
        }

def create_structured_json(text_chunks: List[Dict[str, Any]], 
                          extracted_tables: List[Dict[str, Any]], 
                          source_file: str) -> Dict[str, Any]:
    """구조화된 JSON 생성 편의 함수"""
    
    generator = StructuredJSONGenerator()
    return generator.generate_structured_document(text_chunks, extracted_tables, source_file) 