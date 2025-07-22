"""
고급 테이블/이미지 파싱 모듈
LayoutParser와 PaddleOCR을 활용한 정교한 테이블/이미지 추출
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

# LayoutParser imports
import layoutparser as lp

# PaddleOCR imports
from paddleocr import PaddleOCR

# 기존 설정 import
from config.settings import Settings

class AdvancedParser:
    """LayoutParser와 PaddleOCR 기반 고급 파싱기"""
    
    def __init__(self, use_gpu: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        
        # LayoutParser 모델 초기화
        self.layout_model = self._init_layout_model()
        
        # PaddleOCR 초기화
        self.ocr_system = self._init_paddle_ocr()
        
        # 임시 디렉토리 생성
        self.temp_dir = Path(tempfile.mkdtemp())
        self.logger.info(f"고급 파싱기 초기화 완료 (GPU: {use_gpu})")
    
    def _init_layout_model(self) -> lp.Detectron2LayoutModel:
        """LayoutParser 모델 초기화"""
        try:
            # Detectron2 기반 레이아웃 모델 (테이블/이미지 감지에 최적화)
            model = lp.Detectron2LayoutModel(
                config_path='lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config',
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8]
            )
            self.logger.info("LayoutParser 모델 초기화 성공")
            return model
        except Exception as e:
            self.logger.error(f"LayoutParser 모델 초기화 실패: {str(e)}")
            raise
    
    def _init_paddle_ocr(self) -> PaddleOCR:
        """PaddleOCR 시스템 초기화"""
        try:
            # 기본 PaddleOCR 시스템
            ocr_system = PaddleOCR(
                use_gpu=self.use_gpu,
                show_log=False,
                lang='en'
            )
            self.logger.info("PaddleOCR 시스템 초기화 성공")
            return ocr_system
        except Exception as e:
            self.logger.error(f"PaddleOCR 시스템 초기화 실패: {str(e)}")
            raise
    
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
    
    def detect_layout_elements(self, image: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """LayoutParser를 사용한 레이아웃 요소 감지"""
        try:
            # LayoutParser로 레이아웃 분석
            layout = self.layout_model.detect(image)
            
            elements = []
            for i, element in enumerate(layout):
                element_info = {
                    'id': f"page_{page_num}_element_{i}",
                    'type': element.type,
                    'confidence': element.score,
                    'bbox': {
                        'x': int(element.block.coordinates[0]),
                        'y': int(element.block.coordinates[1]),
                        'width': int(element.block.coordinates[2] - element.block.coordinates[0]),
                        'height': int(element.block.coordinates[3] - element.block.coordinates[1])
                    },
                    'page_num': page_num
                }
                elements.append(element_info)
            
            self.logger.info(f"페이지 {page_num} 레이아웃 감지 완료: {len(elements)}개 요소")
            return elements
            
        except Exception as e:
            self.logger.error(f"레이아웃 감지 실패 (페이지 {page_num}): {str(e)}")
            return []
    
    def extract_table_content(self, image: np.ndarray, bbox: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """PaddleOCR을 사용한 테이블 내용 추출"""
        try:
            # 테이블 영역 자르기
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            table_image = image[y:y+h, x:x+w]
            
            # 임시 파일로 저장
            temp_path = self.temp_dir / f"table_temp_{bbox['x']}_{bbox['y']}.png"
            cv2.imwrite(str(temp_path), table_image)
            
            # PaddleOCR로 텍스트 추출
            result = self.ocr_system.ocr(str(temp_path), cls=True)
            
            if result and len(result) > 0:
                # 텍스트 추출
                texts = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0]  # 텍스트 내용
                        confidence = line[1][1]  # 신뢰도
                        texts.append({
                            'text': text,
                            'confidence': confidence
                        })
                
                # 간단한 테이블 구조 생성
                if texts:
                    # 텍스트를 DataFrame으로 변환
                    df_data = []
                    for text_info in texts:
                        df_data.append([text_info['text']])
                    
                    df = pd.DataFrame(df_data, columns=['Content'])
                    
                    # 결과 구성
                    extracted_table = {
                        'texts': texts,
                        'dataframe': df,
                        'bbox': bbox,
                        'extraction_method': 'PaddleOCR_Basic'
                    }
                    
                    # 임시 파일 삭제
                    temp_path.unlink(missing_ok=True)
                    
                    return extracted_table
            
            # 임시 파일 삭제
            temp_path.unlink(missing_ok=True)
            return None
            
        except Exception as e:
            self.logger.error(f"테이블 내용 추출 실패: {str(e)}")
            return None
    
    def extract_image_file(self, pdf_path: str, bbox: Dict[str, int], page_num: int) -> Optional[Dict[str, Any]]:
        """PyMuPDF를 사용한 고품질 이미지 추출"""
        try:
            doc = fitz.open(pdf_path)
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
                        'bbox': bbox,
                        'extraction_method': 'PyMuPDF_direct'
                    }
                    
                    doc.close()
                    return image_info
                    
                except Exception as e:
                    self.logger.warning(f"이미지 추출 실패 (페이지 {page_num + 1}, 이미지 {img_index}): {str(e)}")
                    continue
            
            doc.close()
            return None
            
        except Exception as e:
            self.logger.error(f"이미지 파일 추출 실패: {str(e)}")
            return None
    
    def process_pdf_advanced(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """고급 PDF 처리 파이프라인"""
        try:
            self.logger.info(f"고급 PDF 처리 시작: {pdf_path}")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 결과 저장용
            tables = []
            images = []
            
            # 1. PDF를 이미지로 변환
            page_images = self.pdf_to_images(pdf_path)
            
            # 2. 각 페이지별 레이아웃 분석 및 요소 추출
            for page_num, page_image in page_images:
                try:
                    # 레이아웃 요소 감지
                    layout_elements = self.detect_layout_elements(page_image, page_num)
                    
                    for element in layout_elements:
                        if element['type'] == 'Table':
                            # 테이블 내용 추출
                            table_data = self.extract_table_content(page_image, element['bbox'])
                            if table_data:
                                table_data['element_info'] = element
                                tables.append(table_data)
                        
                        elif element['type'] == 'Figure':
                            # 이미지 파일 추출
                            image_data = self.extract_image_file(pdf_path, element['bbox'], page_num)
                            if image_data:
                                image_data['element_info'] = element
                                images.append(image_data)
                
                except Exception as e:
                    self.logger.warning(f"페이지 처리 실패 (페이지 {page_num}): {str(e)}")
                    continue
            
            # 3. 결과 요약
            result = {
                'total_pages': len(page_images),
                'extracted_tables': len(tables),
                'extracted_images': len(images),
                'tables': tables,
                'images': images,
                'processing_method': 'AdvancedParser'
            }
            
            self.logger.info(f"고급 PDF 처리 완료: 테이블 {len(tables)}개, 이미지 {len(images)}개")
            return result
            
        except Exception as e:
            self.logger.error(f"고급 PDF 처리 실패: {str(e)}")
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