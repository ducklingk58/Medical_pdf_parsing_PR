"""
간단한 고급 테이블/이미지 파싱 모듈
복잡한 의존성 없이 기본적인 테이블/이미지 추출
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

class SimpleAdvancedParser:
    """간단한 고급 파싱기 - 기본적인 테이블/이미지 추출"""
    
    def __init__(self, use_gpu: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # 임시 디렉토리 생성
        self.temp_dir = Path(tempfile.mkdtemp())
        self.logger.info(f"간단한 고급 파싱기 초기화 완료 (GPU: {use_gpu})")
    
    def pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[Tuple[int, np.ndarray]]:
        """PDF를 고해상도 이미지로 변환"""
        try:
            self.logger.info(f"PDF를 이미지로 변환 중: {pdf_path}")
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 고해상도 이미지로 렌더링
                mat = fitz.Matrix(dpi/72, dpi/72)  # DPI 설정
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Image로 변환
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # OpenCV 형식으로 변환
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                images.append((page_num, cv_image))
                
                # 메모리 해제
                pix = None
            
            doc.close()
            self.logger.info(f"PDF 변환 완료: {len(images)} 페이지")
            return images
            
        except Exception as e:
            self.logger.error(f"PDF 이미지 변환 실패: {str(e)}")
            raise
    
    def detect_table_regions(self, image: np.ndarray) -> List[Dict[str, int]]:
        """간단한 테이블 영역 감지 (선 감지 기반)"""
        try:
            # 그레이스케일 변환
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 엣지 감지
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # 선 감지
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, 
                                  minLineLength=100, maxLineGap=10)
            
            if lines is None:
                return []
            
            # 수평선과 수직선 분리
            horizontal_lines = []
            vertical_lines = []
            
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y2 - y1) < abs(x2 - x1):  # 수평선
                    horizontal_lines.append((y1, y2))
                else:  # 수직선
                    vertical_lines.append((x1, x2))
            
            # 테이블 영역 추정
            table_regions = []
            if len(horizontal_lines) >= 2 and len(vertical_lines) >= 2:
                # 간단한 영역 계산
                y_coords = [y for line in horizontal_lines for y in line]
                x_coords = [x for line in vertical_lines for x in line]
                
                if y_coords and x_coords:
                    min_y, max_y = min(y_coords), max(y_coords)
                    min_x, max_x = min(x_coords), max(x_coords)
                    
                    table_regions.append({
                        'x': min_x,
                        'y': min_y,
                        'width': max_x - min_x,
                        'height': max_y - min_y
                    })
            
            return table_regions
            
        except Exception as e:
            self.logger.error(f"테이블 영역 감지 실패: {str(e)}")
            return []
    
    def extract_table_content_simple(self, image: np.ndarray, bbox: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """간단한 테이블 내용 추출"""
        try:
            # 테이블 영역 자르기
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            table_image = image[y:y+h, x:x+w]
            
            # 그레이스케일 변환
            gray = cv2.cvtColor(table_image, cv2.COLOR_BGR2GRAY)
            
            # 이진화
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 윤곽선 찾기
            contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # 셀 영역 추출
            cells = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:  # 작은 노이즈 제거
                    x, y, w, h = cv2.boundingRect(contour)
                    cells.append((x, y, w, h))
            
            # 간단한 테이블 구조 생성
            if cells:
                # 셀을 위치에 따라 정렬
                cells.sort(key=lambda cell: (cell[1], cell[0]))  # y, x 순으로 정렬
                
                # DataFrame 생성
                df_data = []
                for i, (x, y, w, h) in enumerate(cells):
                    df_data.append([f"Cell_{i+1}", x, y, w, h])
                
                df = pd.DataFrame(df_data, columns=['Cell_ID', 'X', 'Y', 'Width', 'Height'])
                
                # 결과 구성
                extracted_table = {
                    'cells': cells,
                    'dataframe': df,
                    'bbox': bbox,
                    'extraction_method': 'SimpleContourDetection'
                }
                
                return extracted_table
            
            return None
            
        except Exception as e:
            self.logger.error(f"테이블 내용 추출 실패: {str(e)}")
            return None
    
    def extract_images_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """PDF에서 이미지 추출"""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 페이지에서 이미지 목록 가져오기
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # 이미지 데이터 추출
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # 이미지 정보
                        image_info = {
                            'page_num': page_num + 1,
                            'image_index': img_index,
                            'width': img[2],
                            'height': img[3],
                            'image_bytes': image_bytes,
                            'format': base_image["ext"],
                            'extraction_method': 'PyMuPDF_direct'
                        }
                        
                        images.append(image_info)
                        
                    except Exception as e:
                        self.logger.warning(f"이미지 추출 실패 (페이지 {page_num + 1}, 이미지 {img_index}): {str(e)}")
                        continue
            
            doc.close()
            return images
            
        except Exception as e:
            self.logger.error(f"이미지 파일 추출 실패: {str(e)}")
            return []
    
    def process_pdf_simple(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """간단한 PDF 처리 파이프라인"""
        try:
            self.logger.info(f"간단한 PDF 처리 시작: {pdf_path}")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 결과 저장용
            tables = []
            images = []
            
            # 1. PDF를 이미지로 변환
            page_images = self.pdf_to_images(pdf_path)
            
            # 2. 각 페이지별 테이블 감지 및 추출
            for page_num, page_image in page_images:
                try:
                    # 테이블 영역 감지
                    table_regions = self.detect_table_regions(page_image)
                    
                    for i, bbox in enumerate(table_regions):
                        # 테이블 내용 추출
                        table_data = self.extract_table_content_simple(page_image, bbox)
                        if table_data:
                            table_data['page_num'] = page_num
                            table_data['table_id'] = f"table_{page_num}_{i+1}"
                            tables.append(table_data)
                
                except Exception as e:
                    self.logger.warning(f"페이지 처리 실패 (페이지 {page_num}): {str(e)}")
                    continue
            
            # 3. 이미지 추출
            images = self.extract_images_from_pdf(pdf_path)
            
            # 4. 결과 요약
            result = {
                'total_pages': len(page_images),
                'extracted_tables': len(tables),
                'extracted_images': len(images),
                'tables': tables,
                'images': images,
                'processing_method': 'SimpleAdvancedParser'
            }
            
            self.logger.info(f"간단한 PDF 처리 완료: 테이블 {len(tables)}개, 이미지 {len(images)}개")
            return result
            
        except Exception as e:
            self.logger.error(f"간단한 PDF 처리 실패: {str(e)}")
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