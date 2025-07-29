import re
import json
from typing import List, Dict, Any, Optional
import logging

class TableToTextConverter:
    """표 데이터를 자연어로 변환하는 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 의약품/의료 관련 키워드 매핑
        self.medical_keywords = {
            '품목': '의약품',
            '성분': '주성분',
            '용량': '용법용량',
            '부작용': '이상반응',
            '효능': '적응증',
            '금기': '금기사항',
            '주의': '주의사항',
            '보관': '저장방법',
            '제조': '제조사',
            '허가': '허가번호'
        }
    
    def convert_table_to_natural_language(self, table_data: Dict[str, Any]) -> Dict[str, str]:
        """표 데이터를 자연어로 변환"""
        try:
            table_structure = table_data.get('structure', {})
            raw_data = table_data.get('table_data', [])
            cell_texts = table_data.get('cell_texts', [])
            
            # 다양한 형태의 표 처리
            if isinstance(raw_data, list) and raw_data:
                if isinstance(raw_data[0], list):
                    # 2차원 배열 형태
                    natural_text = self._convert_2d_array_table(raw_data, table_data)
                else:
                    # 1차원 배열 형태
                    natural_text = self._convert_1d_array_table(raw_data, table_data)
            elif cell_texts:
                # cell_texts 기반 변환
                natural_text = self._convert_cell_texts_table(cell_texts, table_data)
            else:
                # 기본 텍스트 추출
                natural_text = table_data.get('extracted_text', '')
            
            # 검색용 키워드 추출
            search_keywords = self._extract_search_keywords(natural_text, table_data)
            
            # 구조화된 설명 생성
            structured_description = self._create_structured_description(table_data)
            
            return {
                'natural_language': natural_text,
                'search_keywords': search_keywords,
                'structured_description': structured_description,
                'table_summary': self._create_table_summary(table_data)
            }
            
        except Exception as e:
            self.logger.error(f"표 자연어 변환 실패: {str(e)}")
            return {
                'natural_language': table_data.get('extracted_text', ''),
                'search_keywords': '',
                'structured_description': '',
                'table_summary': ''
            }
    
    def _convert_2d_array_table(self, data: List[List[str]], table_info: Dict) -> str:
        """2차원 배열 형태의 표를 자연어로 변환"""
        if not data or len(data) < 2:
            return ""
        
        # 첫 번째 행을 헤더로 간주
        headers = data[0]
        rows = data[1:]
        
        sentences = []
        
        # 표 소개
        table_intro = f"이 표는 {len(rows)}개의 항목에 대한 {', '.join(headers)} 정보를 보여줍니다."
        sentences.append(table_intro)
        
        # 각 행을 자연어로 변환
        for i, row in enumerate(rows):
            if len(row) >= len(headers):
                row_description = self._create_row_description(headers, row, i+1)
                if row_description:
                    sentences.append(row_description)
        
        return " ".join(sentences)
    
    def _convert_1d_array_table(self, data: List[str], table_info: Dict) -> str:
        """1차원 배열 형태의 표를 자연어로 변환"""
        if not data:
            return ""
        
        # 키-값 쌍으로 해석 시도
        key_value_pairs = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                key = data[i].strip()
                value = data[i + 1].strip()
                if key and value:
                    key_value_pairs.append((key, value))
        
        if key_value_pairs:
            descriptions = []
            for key, value in key_value_pairs:
                medical_key = self.medical_keywords.get(key, key)
                descriptions.append(f"{medical_key}은 {value}입니다")
            
            return f"이 표에 따르면, {', '.join(descriptions)}."
        else:
            # 단순 나열
            return f"표에는 다음 정보가 포함되어 있습니다: {', '.join(data)}."
    
    def _convert_cell_texts_table(self, cell_texts: List[Dict], table_info: Dict) -> str:
        """cell_texts 기반 표 변환"""
        if not cell_texts:
            return ""
        
        # 셀 텍스트들을 행/열로 정렬
        cells_by_position = {}
        for cell in cell_texts:
            row = cell.get('row', 0)
            col = cell.get('col', 0)
            text = cell.get('text', '').strip()
            
            if text:
                if row not in cells_by_position:
                    cells_by_position[row] = {}
                cells_by_position[row][col] = text
        
        if not cells_by_position:
            return ""
        
        # 첫 번째 행을 헤더로 시도
        if 0 in cells_by_position:
            headers = [cells_by_position[0].get(col, '') for col in sorted(cells_by_position[0].keys())]
            
            sentences = []
            for row_idx in sorted(cells_by_position.keys())[1:]:  # 헤더 제외
                row_data = cells_by_position[row_idx]
                row_values = [row_data.get(col, '') for col in sorted(row_data.keys())]
                
                if len(row_values) >= len(headers) and any(row_values):
                    row_desc = self._create_row_description(headers, row_values, row_idx)
                    if row_desc:
                        sentences.append(row_desc)
            
            if sentences:
                return f"표에는 {', '.join(headers)} 정보가 포함되어 있습니다. " + " ".join(sentences)
        
        # 헤더 구분이 어려운 경우 단순 나열
        all_texts = []
        for row_idx in sorted(cells_by_position.keys()):
            for col_idx in sorted(cells_by_position[row_idx].keys()):
                text = cells_by_position[row_idx][col_idx]
                if text:
                    all_texts.append(text)
        
        return f"표에는 다음 정보들이 포함되어 있습니다: {', '.join(all_texts)}."
    
    def _create_row_description(self, headers: List[str], values: List[str], row_num: int) -> str:
        """행 데이터를 자연어 설명으로 변환"""
        if not headers or not values:
            return ""
        
        descriptions = []
        for i, (header, value) in enumerate(zip(headers, values)):
            if header.strip() and value.strip():
                # 의료 용어 매핑 적용
                medical_header = self.medical_keywords.get(header.strip(), header.strip())
                descriptions.append(f"{medical_header}은 {value.strip()}")
        
        if descriptions:
            return f"항목 {row_num}의 경우 {', '.join(descriptions)}입니다."
        return ""
    
    def _extract_search_keywords(self, text: str, table_info: Dict) -> str:
        """검색용 키워드 추출"""
        keywords = set()
        
        # 의료 관련 키워드 추출
        for keyword in self.medical_keywords.values():
            if keyword in text:
                keywords.add(keyword)
        
        # 표 메타데이터에서 키워드 추출
        if 'caption' in table_info:
            keywords.add(table_info['caption'])
        
        # 숫자가 포함된 중요 정보 추출
        number_patterns = re.findall(r'\d+(?:\.\d+)?(?:mg|g|ml|개|명|건|%)', text)
        keywords.update(number_patterns)
        
        return ', '.join(sorted(keywords))
    
    def _create_structured_description(self, table_info: Dict) -> str:
        """구조화된 표 설명 생성"""
        structure = table_info.get('structure', {})
        rows = structure.get('rows', 0)
        columns = structure.get('columns', 0)
        page_num = table_info.get('page_number', 1)
        
        desc_parts = []
        desc_parts.append(f"페이지 {page_num}에 위치한 표")
        
        if rows and columns:
            desc_parts.append(f"{rows}행 {columns}열 구조")
        
        extraction_tool = table_info.get('extraction_tool', '')
        if extraction_tool:
            desc_parts.append(f"{extraction_tool}로 추출됨")
        
        confidence = table_info.get('confidence_score', 0)
        if confidence > 0:
            desc_parts.append(f"신뢰도 {confidence:.1%}")
        
        return ", ".join(desc_parts)
    
    def _create_table_summary(self, table_info: Dict) -> str:
        """표 요약 정보 생성"""
        summary_parts = []
        
        # 표 기본 정보
        table_id = table_info.get('table_id', 'unknown')
        summary_parts.append(f"표 ID: {table_id}")
        
        # 데이터 양
        table_data = table_info.get('table_data', [])
        if isinstance(table_data, list):
            data_count = len([item for item in table_data if item])
            summary_parts.append(f"데이터 항목: {data_count}개")
        
        # 위치 정보
        page_num = table_info.get('page_number', 1)
        summary_parts.append(f"위치: {page_num}페이지")
        
        return " | ".join(summary_parts)

    def create_table_chunks(self, table_data: Dict[str, Any], chunk_id_prefix: str = "table") -> List[Dict[str, Any]]:
        """표 데이터로부터 검색용 청크들 생성"""
        try:
            # 자연어 변환
            converted = self.convert_table_to_natural_language(table_data)
            
            chunks = []
            
            # 1. 메인 표 청크 (전체 표 내용)
            main_chunk = {
                "id": f"{chunk_id_prefix}_{table_data.get('table_id', 'unknown')}_main",
                "type": "table",
                "subtype": "full_table",
                "text": converted['natural_language'],
                "table_id": table_data.get('table_id'),
                "page_number": table_data.get('page_number', 1),
                "coordinates": table_data.get('coordinates', []),
                "structure": table_data.get('structure', {}),
                "search_keywords": converted['search_keywords'],
                "word_count": len(converted['natural_language'].split()),
                "token_estimate": len(converted['natural_language'].split()) * 1.3,
                "extraction_tool": table_data.get('extraction_tool', ''),
                "confidence_score": table_data.get('confidence_score', 0.0),
                "original_table_data": table_data.get('table_data', [])
            }
            chunks.append(main_chunk)
            
            # 2. 요약 청크 (검색 최적화)
            if converted['table_summary']:
                summary_chunk = {
                    "id": f"{chunk_id_prefix}_{table_data.get('table_id', 'unknown')}_summary",
                    "type": "table",
                    "subtype": "summary",
                    "text": converted['table_summary'],
                    "table_id": table_data.get('table_id'),
                    "page_number": table_data.get('page_number', 1),
                    "word_count": len(converted['table_summary'].split()),
                    "token_estimate": len(converted['table_summary'].split()) * 1.3,
                    "parent_chunk_id": main_chunk["id"]
                }
                chunks.append(summary_chunk)
            
            # 3. 개별 셀 청크 (상세 검색용)
            cell_texts = table_data.get('cell_texts', [])
            if cell_texts:
                for i, cell in enumerate(cell_texts):
                    cell_text = cell.get('text', '').strip()
                    if cell_text and len(cell_text) > 2:  # 의미있는 텍스트만
                        cell_chunk = {
                            "id": f"{chunk_id_prefix}_{table_data.get('table_id', 'unknown')}_cell_{i}",
                            "type": "table",
                            "subtype": "cell",
                            "text": cell_text,
                            "table_id": table_data.get('table_id'),
                            "page_number": table_data.get('page_number', 1),
                            "cell_position": {"row": cell.get('row', 0), "col": cell.get('col', 0)},
                            "word_count": len(cell_text.split()),
                            "token_estimate": len(cell_text.split()) * 1.3,
                            "parent_chunk_id": main_chunk["id"]
                        }
                        chunks.append(cell_chunk)
            
            self.logger.info(f"표 {table_data.get('table_id')}에서 {len(chunks)}개 청크 생성")
            return chunks
            
        except Exception as e:
            self.logger.error(f"표 청크 생성 실패: {str(e)}")
            # 기본 청크라도 생성
            return [{
                "id": f"{chunk_id_prefix}_{table_data.get('table_id', 'unknown')}_basic",
                "type": "table",
                "subtype": "basic",
                "text": table_data.get('extracted_text', ''),
                "table_id": table_data.get('table_id'),
                "page_number": table_data.get('page_number', 1),
                "word_count": len(table_data.get('extracted_text', '').split()),
                "token_estimate": len(table_data.get('extracted_text', '').split()) * 1.3,
                "error": str(e)
            }] 