"""
PDF 테이블 파싱 모듈
PaddleOCR과 LayoutParser를 활용한 정확한 테이블/표 내용 추출
"""

import os
import cv2
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
from PIL import Image
import io
import base64
import uuid
from datetime import datetime

# LayoutParser imports
try:
    import layoutparser as lp
    LAYOUTPARSER_AVAILABLE = True
except ImportError:
    LAYOUTPARSER_AVAILABLE = False
    print("LayoutParser를 사용할 수 없습니다. 기본 모드로 실행됩니다.")

# PaddleOCR imports
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("PaddleOCR을 사용할 수 없습니다.")

class TableParser:
    """PDF 테이블 파싱 전용 클래스"""
    
    def __init__(self, use_gpu: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # PaddleOCR 초기화
        self.ocr_system = self._init_paddle_ocr()
        
        # LayoutParser 모델 초기화
        self.layout_model = self._init_layout_model()
        
        # 임시 디렉토리 생성
        self.temp_dir = Path(tempfile.mkdtemp())
        self.logger.info(f"테이블 파서 초기화 완료 (GPU: {use_gpu})")
    
    def _init_paddle_ocr(self) -> Optional[PaddleOCR]:
        """PaddleOCR 시스템 초기화"""
        if not PADDLEOCR_AVAILABLE:
            self.logger.warning("PaddleOCR을 사용할 수 없습니다.")
            return None
            
        try:
            # 가장 기본적인 초기화
            ocr_system = PaddleOCR()  # 모든 매개변수 제거
            self.logger.info("PaddleOCR 시스템 초기화 성공 (기본 설정)")
            return ocr_system
        except Exception as e:
            self.logger.error(f"PaddleOCR 초기화 실패: {str(e)}")
            return None
    
    def _init_layout_model(self):
        """LayoutParser 모델 초기화"""
        if not LAYOUTPARSER_AVAILABLE:
            self.logger.warning("LayoutParser를 사용할 수 없습니다.")
            return None
            
        try:
            # 사용 가능한 모델 확인
            if hasattr(lp, 'PaddleDetectionLayoutModel'):
                # PaddleDetection 기반 모델 사용 (threshold 매개변수 제거)
                try:
                    model = lp.PaddleDetectionLayoutModel(
                        config_path='lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config',
                        label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
                    )
                    self.logger.info("LayoutParser PaddleDetection 모델 초기화 성공")
                    return model
                except Exception as e:
                    self.logger.warning(f"PaddleDetectionLayoutModel 초기화 실패: {str(e)}")
                    return None
            else:
                self.logger.warning("LayoutParser 고급 모델을 사용할 수 없습니다.")
                return None
        except Exception as e:
            self.logger.error(f"LayoutParser 모델 초기화 실패: {str(e)}")
            return None
    
    def pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[Tuple[int, np.ndarray]]:
        """PDF를 고해상도 이미지로 변환"""
        try:
            self.logger.info(f"PDF를 이미지로 변환 중: {pdf_path}")
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 고해상도 이미지로 변환
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Image로 변환
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # OpenCV 형식으로 변환
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                images.append((page_num, cv_image))
                
                self.logger.info(f"페이지 {page_num + 1} 변환 완료")
            
            doc.close()
            self.logger.info(f"총 {len(images)}페이지 변환 완료")
            return images
            
        except Exception as e:
            self.logger.error(f"PDF 이미지 변환 실패: {str(e)}")
            return []  # 빈 리스트 반환으로 변경
    
    def detect_tables(self, image: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """테이블 영역 감지"""
        tables = []
        
        try:
            if self.layout_model:
                # LayoutParser를 사용한 테이블 감지
                layout = self.layout_model.detect(image)
                
                for element in layout:
                    if element.type == "Table":
                        bbox = element.block.coordinates
                        tables.append({
                            'bbox': {
                                'x': int(bbox[0]),
                                'y': int(bbox[1]),
                                'width': int(bbox[2] - bbox[0]),
                                'height': int(bbox[3] - bbox[1])
                            },
                            'confidence': element.score,
                            'page_num': page_num + 1,
                            'detection_method': 'LayoutParser'
                        })
            else:
                # OpenCV를 사용한 기본 테이블 감지
                tables = self._detect_tables_opencv(image, page_num)
                
        except Exception as e:
            self.logger.error(f"테이블 감지 실패: {str(e)}")
            # 기본 감지로 폴백
            tables = self._detect_tables_opencv(image, page_num)
        
        return tables
    
    def _detect_tables_opencv(self, image: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """OpenCV를 사용한 기본 테이블 감지"""
        tables = []
        
        try:
            # 그레이스케일 변환
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 이진화
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 수평선과 수직선 감지
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            
            horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
            
            # 테이블 구조 생성
            table_structure = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
            
            # 윤곽선 찾기
            contours, _ = cv2.findContours(table_structure, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 1000:  # 최소 면적 필터
                    x, y, w, h = cv2.boundingRect(contour)
                    tables.append({
                        'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                        'confidence': 0.7,
                        'page_num': page_num + 1,
                        'detection_method': 'OpenCV_contour'
                    })
                    
        except Exception as e:
            self.logger.error(f"OpenCV 테이블 감지 실패: {str(e)}")
        
        return tables
    
    def extract_table_structure(self, image: np.ndarray, bbox: Dict[str, int]) -> Dict[str, Any]:
        """테이블 구조 분석 및 셀 추출"""
        try:
            # 테이블 영역 자르기
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            table_image = image[y:y+h, x:x+w]
            
            # 그레이스케일 변환
            gray = cv2.cvtColor(table_image, cv2.COLOR_BGR2GRAY)
            
            # 이진화
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 수평선과 수직선 감지
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w//10, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h//10))
            
            horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
            
            # 격자 생성
            grid = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
            
            # 셀 윤곽선 찾기
            contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # 셀 정보 수집
            cells = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:  # 최소 셀 면적
                    cell_x, cell_y, cell_w, cell_h = cv2.boundingRect(contour)
                    cells.append({
                        'x': cell_x,
                        'y': cell_y,
                        'width': cell_w,
                        'height': cell_h,
                        'area': area
                    })
            
            # 셀을 행/열로 정렬
            cells = sorted(cells, key=lambda c: (c['y'], c['x']))
            
            # 행과 열 수 계산
            if cells:
                # Y 좌표로 그룹화하여 행 수 계산
                y_coords = sorted(list(set([cell['y'] for cell in cells])))
                x_coords = sorted(list(set([cell['x'] for cell in cells])))
                
                rows = len(y_coords)
                cols = len(x_coords)
            else:
                rows = cols = 0
            
            return {
                'cells': cells,
                'rows': rows,
                'columns': cols,
                'grid_image': grid
            }
            
        except Exception as e:
            self.logger.error(f"테이블 구조 분석 실패: {str(e)}")
            return {'cells': [], 'rows': 0, 'columns': 0, 'grid_image': None}
    
    def extract_cell_text(self, image: np.ndarray, cell_bbox: Dict[str, int]) -> str:
        """개별 셀의 텍스트 추출"""
        try:
            if not self.ocr_system:
                return ""
            
            # 셀 영역 자르기
            x, y, w, h = cell_bbox['x'], cell_bbox['y'], cell_bbox['width'], cell_bbox['height']
            cell_image = image[y:y+h, x:x+w]
            
            # 임시 파일로 저장
            temp_path = self.temp_dir / f"cell_{uuid.uuid4().hex[:8]}.png"
            cv2.imwrite(str(temp_path), cell_image)
            
            # PaddleOCR로 텍스트 추출
            result = self.ocr_system.ocr(str(temp_path), cls=True)
            
            # 임시 파일 삭제
            temp_path.unlink(missing_ok=True)
            
            if result and len(result) > 0 and result[0]:
                # 모든 텍스트 결합
                texts = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0].strip()
                        if text:
                            texts.append(text)
                
                return " ".join(texts)
            
            return ""
            
        except Exception as e:
            self.logger.error(f"셀 텍스트 추출 실패: {str(e)}")
            return ""
    
    def parse_table_content(self, image: np.ndarray, bbox: Dict[str, int], page_num: int) -> Dict[str, Any]:
        """테이블 내용 완전 파싱"""
        try:
            # 테이블 구조 분석
            structure = self.extract_table_structure(image, bbox)
            
            # 테이블 영역 자르기
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            table_image = image[y:y+h, x:x+w]
            
            # 셀별 텍스트 추출
            table_data = []
            cell_texts = []
            
            for cell in structure['cells']:
                text = self.extract_cell_text(table_image, cell)
                cell_texts.append({
                    'text': text,
                    'bbox': cell,
                    'row': cell.get('row', 0),
                    'col': cell.get('col', 0)
                })
            
            # 2차원 배열로 구조화
            if structure['rows'] > 0 and structure['columns'] > 0:
                table_array = [['' for _ in range(structure['columns'])] for _ in range(structure['rows'])]
                
                # 셀 텍스트를 배열에 배치
                for cell_text in cell_texts:
                    row = cell_text.get('row', 0)
                    col = cell_text.get('col', 0)
                    if row < structure['rows'] and col < structure['columns']:
                        table_array[row][col] = cell_text['text']
                
                table_data = table_array
            else:
                # 구조화되지 않은 경우 단순 리스트
                table_data = [cell['text'] for cell in cell_texts]
            
            # 결과 구성
            result = {
                'table_id': str(uuid.uuid4()),
                'page_number': page_num,
                'bbox': bbox,
                'structure': {
                    'rows': structure['rows'],
                    'columns': structure['columns'],
                    'cells': structure['cells']
                },
                'table_data': table_data,
                'cell_texts': cell_texts,
                'extraction_method': 'PaddleOCR_Structured',
                'extraction_timestamp': datetime.now().isoformat(),
                'confidence': 0.8
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"테이블 내용 파싱 실패: {str(e)}")
            return None
    
    def process_pdf_tables(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """PDF 테이블 처리 메인 파이프라인"""
        try:
            self.logger.info(f"PDF 테이블 처리 시작: {pdf_path}")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 결과 저장용
            all_tables = []
            table_files = []
            
            # 1. PDF를 이미지로 변환
            page_images = self.pdf_to_images(pdf_path)
            
            # page_images가 올바른 형식인지 확인
            if not isinstance(page_images, list):
                self.logger.error(f"pdf_to_images가 올바른 형식을 반환하지 않았습니다: {type(page_images)}")
                return {
                    'pdf_path': pdf_path,
                    'total_pages': 0,
                    'total_tables': 0,
                    'table_files': [],
                    'processing_timestamp': datetime.now().isoformat(),
                    'processing_method': 'TableParser_v1.0',
                    'error': 'Invalid page_images format'
                }
            
            # 2. 각 페이지별 테이블 감지 및 파싱
            for page_num, page_image in page_images:
                try:
                    self.logger.info(f"페이지 {page_num + 1} 처리 중...")
                    
                    # 테이블 감지
                    detected_tables = self.detect_tables(page_image, page_num)
                    self.logger.info(f"페이지 {page_num + 1}에서 {len(detected_tables)}개 테이블 감지")
                    
                    # 각 테이블 파싱
                    for i, table_bbox in enumerate(detected_tables):
                        try:
                            # 테이블 내용 파싱
                            table_content = self.parse_table_content(page_image, table_bbox['bbox'], page_num)
                            
                            if table_content:
                                # 고유 ID 생성
                                table_id = f"table_{page_num + 1}_{i + 1}_{uuid.uuid4().hex[:8]}"
                                table_content['table_id'] = table_id
                                
                                # 파일로 저장
                                table_file = output_path / f"{table_id}.json"
                                with open(table_file, 'w', encoding='utf-8') as f:
                                    json.dump(table_content, f, ensure_ascii=False, indent=2)
                                
                                all_tables.append(table_content)
                                table_files.append(str(table_file))
                                
                                self.logger.info(f"테이블 {table_id} 파싱 완료")
                            
                        except Exception as e:
                            self.logger.error(f"개별 테이블 파싱 실패: {str(e)}")
                            continue
                
                except Exception as e:
                    self.logger.error(f"페이지 {page_num + 1} 처리 실패: {str(e)}")
                    continue
            
            # 3. 결과 요약
            result = {
                'pdf_path': pdf_path,
                'total_pages': len(page_images),
                'total_tables': len(all_tables),
                'table_files': table_files,
                'processing_timestamp': datetime.now().isoformat(),
                'processing_method': 'TableParser_v1.0'
            }
            
            # 요약 파일 저장
            summary_file = output_path / 'table_parsing_summary.json'
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"PDF 테이블 처리 완료: {len(all_tables)}개 테이블 파싱됨")
            return result
            
        except Exception as e:
            self.logger.error(f"PDF 테이블 처리 실패: {str(e)}")
            raise
    
    def cleanup(self):
        """임시 파일 정리"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.logger.info("임시 파일 정리 완료")
        except Exception as e:
            self.logger.warning(f"임시 파일 정리 실패: {str(e)}")
    
    def __del__(self):
        """소멸자"""
        self.cleanup() 