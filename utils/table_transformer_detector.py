#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Microsoft Table Transformer 기반 표 감지 모듈
Table Detection using Microsoft Table Transformer
"""

import torch
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
import logging
from pathlib import Path
import uuid
import json
import io
import pandas as pd

try:
    from transformers import AutoImageProcessor, TableTransformerForObjectDetection
    TRANSFORMER_AVAILABLE = True
except ImportError:
    TRANSFORMER_AVAILABLE = False
    print("⚠️ Table Transformer 라이브러리가 설치되지 않았습니다.")
    print("설치: pip install transformers torch torchvision")

class TableTransformerDetector:
    """Microsoft Table Transformer를 사용한 고성능 표 감지"""
    
    def __init__(self, device: str = "auto"):
        """
        초기화
        
        Args:
            device: 사용할 디바이스 ("auto", "cpu", "cuda")
        """
        self.logger = logging.getLogger(__name__)
        
        if not TRANSFORMER_AVAILABLE:
            raise ImportError("Table Transformer 라이브러리가 필요합니다. pip install transformers torch torchvision")
        
        # 디바이스 설정
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self.logger.info(f"Table Transformer 디바이스: {self.device}")
        
        # 모델 로드
        self.model_name = "microsoft/table-transformer-detection"
        self._load_model()
        
    def _load_model(self):
        """Table Transformer 모델 로드"""
        try:
            self.logger.info("Table Transformer 모델 로딩 중...")
            
            # 이미지 프로세서와 모델 로드
            self.image_processor = AutoImageProcessor.from_pretrained(self.model_name)
            self.model = TableTransformerForObjectDetection.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            self.logger.info("✅ Table Transformer 모델 로드 완료")
            
        except Exception as e:
            self.logger.error(f"❌ Table Transformer 모델 로드 실패: {str(e)}")
            raise
    
    def pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[np.ndarray]:
        """PDF를 이미지로 변환"""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 고해상도로 렌더링
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Image로 변환
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                
                images.append(np.array(img))
                
            doc.close()
            self.logger.info(f"PDF를 {len(images)}개 이미지로 변환 완료")
            return images
            
        except Exception as e:
            self.logger.error(f"PDF 이미지 변환 실패: {str(e)}")
            return []
    
    def detect_tables_in_image(self, image: np.ndarray, confidence_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """단일 이미지에서 표 감지"""
        try:
            # PIL Image로 변환
            if isinstance(image, np.ndarray):
                pil_image = Image.fromarray(image)
            else:
                pil_image = image
            
            # 이미지 전처리
            inputs = self.image_processor(images=pil_image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 추론 실행
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            # 결과 후처리
            target_sizes = torch.tensor([pil_image.size[::-1]]).to(self.device)
            results = self.image_processor.post_process_object_detection(
                outputs, 
                threshold=confidence_threshold, 
                target_sizes=target_sizes
            )[0]
            
            # 표 정보 추출
            tables = []
            for i, (score, label, box) in enumerate(zip(
                results["scores"], results["labels"], results["boxes"]
            )):
                # 라벨이 "table"인 경우만 (Table Transformer는 table/table rotated 감지)
                if score >= confidence_threshold:
                    x1, y1, x2, y2 = box.cpu().numpy()
                    
                    table_info = {
                        "table_id": str(uuid.uuid4()),
                        "bbox": {
                            "x": float(x1),
                            "y": float(y1), 
                            "width": float(x2 - x1),
                            "height": float(y2 - y1)
                        },
                        "confidence_score": float(score),
                        "label_id": int(label),
                        "extraction_tool": "Microsoft_Table_Transformer",
                        "model_name": self.model_name
                    }
                    tables.append(table_info)
            
            self.logger.info(f"이미지에서 {len(tables)}개 표 감지됨")
            return tables
            
        except Exception as e:
            self.logger.error(f"이미지 표 감지 실패: {str(e)}")
            return []
    
    def detect_tables_in_pdf(self, pdf_path: str, confidence_threshold: float = 0.7, dpi: int = 200) -> Dict[str, Any]:
        """PDF 파일에서 표 감지"""
        try:
            self.logger.info(f"Table Transformer로 PDF 표 감지 시작: {pdf_path}")
            
            # PDF를 이미지로 변환
            images = self.pdf_to_images(pdf_path, dpi=dpi)
            
            if not images:
                return {
                    "success": False,
                    "error": "PDF 이미지 변환 실패",
                    "tables": []
                }
            
            all_tables = []
            
            # 각 페이지에서 표 감지
            for page_num, image in enumerate(images):
                page_tables = self.detect_tables_in_image(image, confidence_threshold)
                
                # 페이지 정보 추가
                for table in page_tables:
                    table["page_number"] = page_num + 1
                    table["coordinates"] = [
                        table["bbox"]["x"],
                        table["bbox"]["y"],
                        table["bbox"]["x"] + table["bbox"]["width"],
                        table["bbox"]["y"] + table["bbox"]["height"]
                    ]
                    all_tables.append(table)
            
            self.logger.info(f"✅ 총 {len(all_tables)}개 표 감지 완료")
            
            return {
                "success": True,
                "pdf_path": pdf_path,
                "total_pages": len(images),
                "total_tables": len(all_tables),
                "tables": all_tables,
                "processing_method": "Table_Transformer_v1.0",
                "model_name": self.model_name,
                "confidence_threshold": confidence_threshold,
                "dpi": dpi
            }
            
        except Exception as e:
            self.logger.error(f"PDF 표 감지 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tables": []
            }
    
    def extract_table_content_with_ocr(self, pdf_path: str, table_bbox: Dict, page_number: int) -> Dict[str, Any]:
        """감지된 표 영역에서 PaddleOCR로 내용 추출"""
        try:
            # PDF에서 해당 페이지와 영역 추출
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_number - 1)
            
            # 표 영역 크롭
            rect = fitz.Rect(
                table_bbox["x"],
                table_bbox["y"],
                table_bbox["x"] + table_bbox["width"],
                table_bbox["y"] + table_bbox["height"]
            )
            
            # 고해상도로 렌더링
            mat = fitz.Matrix(3.0, 3.0)  # 3배 확대로 OCR 정확도 향상
            pix = page.get_pixmap(matrix=mat, clip=rect)
            
            # PIL Image로 변환
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            
            doc.close()
            
            # PaddleOCR로 텍스트 추출
            try:
                # PaddleOCR 초기화 (간단한 설정)
                try:
                    from paddleocr import PaddleOCR
                    ocr = PaddleOCR(use_angle_cls=True, lang='en')  # 영어 모드
                except:
                    # 언어 폴백
                    try:
                        ocr = PaddleOCR(use_angle_cls=True, lang='ch')
                    except:
                        ocr = PaddleOCR(use_angle_cls=True)
                
                # OCR 실행
                result = ocr.ocr(np.array(img), cls=True)
                
                # 결과 처리
                extracted_texts = []
                cell_texts = []
                
                if result and result[0]:
                    for idx, line in enumerate(result[0]):
                        if line:
                            # 텍스트와 신뢰도 추출
                            bbox, (text, confidence) = line
                            if confidence > 0.5:  # 50% 이상 신뢰도만
                                extracted_texts.append(text)
                                
                                # 셀 정보 생성 (간단한 행/열 추정)
                                cell_info = {
                                    "text": text,
                                    "confidence": confidence,
                                    "bbox": bbox,
                                    "row": idx // 3,  # 대략적인 행 추정
                                    "col": idx % 3    # 대략적인 열 추정
                                }
                                cell_texts.append(cell_info)
                
                # 전체 텍스트 결합
                full_text = " ".join(extracted_texts)
                
                return {
                    "extracted_text": full_text,
                    "table_data": [],  # 구조화는 별도 처리
                    "cell_texts": cell_texts,
                    "ocr_method": "PaddleOCR",
                    "total_cells": len(cell_texts),
                    "avg_confidence": sum(c.get('confidence', 0) for c in cell_texts) / len(cell_texts) if cell_texts else 0
                }
                
            except Exception as ocr_error:
                self.logger.warning(f"PaddleOCR 실패, PyMuPDF 텍스트 추출 시도: {str(ocr_error)}")
                
                # 폴백: PyMuPDF 텍스트 추출
                doc = fitz.open(pdf_path)
                page = doc.load_page(page_number - 1)
                text_dict = page.get_text("dict")
                
                # 표 영역 내 텍스트 추출
                extracted_text = ""
                for block in text_dict["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                bbox = span["bbox"]
                                # 표 영역 내에 있는지 확인
                                if (table_bbox["x"] <= bbox[0] <= table_bbox["x"] + table_bbox["width"] and
                                    table_bbox["y"] <= bbox[1] <= table_bbox["y"] + table_bbox["height"]):
                                    extracted_text += span["text"] + " "
                
                doc.close()
                
                return {
                    "extracted_text": extracted_text.strip(),
                    "table_data": [],
                    "cell_texts": [],
                    "ocr_method": "PyMuPDF_fallback",
                    "note": "PaddleOCR 실패로 PyMuPDF 사용"
                }
            
        except Exception as e:
            self.logger.error(f"표 내용 추출 실패: {str(e)}")
            return {
                "extracted_text": f"Table region detected on page {page_number}",
                "table_data": [],
                "cell_texts": [],
                "error": str(e),
                "ocr_method": "failed"
            }
    
    def process_pdf_with_table_transformer(self, pdf_path: str, output_dir: str = None, confidence_threshold: float = 0.7, 
                                          create_visualization: bool = True) -> Dict[str, Any]:
        """Table Transformer를 사용한 전체 PDF 처리"""
        try:
            # 1. 표 감지
            detection_result = self.detect_tables_in_pdf(pdf_path, confidence_threshold)
            
            if not detection_result["success"]:
                return detection_result
            
            # 2. 각 표에서 내용 추출
            enhanced_tables = []
            for i, table in enumerate(detection_result["tables"]):
                self.logger.info(f"표 {i+1}/{len(detection_result['tables'])} 내용 추출 중...")
                
                # 표 내용 추출
                content = self.extract_table_content_with_ocr(
                    pdf_path, 
                    table["bbox"], 
                    table["page_number"]
                )
                
                # 표 정보와 내용 결합
                enhanced_table = {**table, **content}
                
                # 추출된 텍스트가 있으면 로그 출력
                if content.get("extracted_text"):
                    preview = content["extracted_text"][:100]
                    self.logger.info(f"표 {i+1} 텍스트 추출: {preview}...")
                
                enhanced_tables.append(enhanced_table)
            
            # 3. 결과 정리
            final_result = {
                **detection_result,
                "tables": enhanced_tables,
                "processing_timestamp": pd.Timestamp.now().isoformat(),
                "extraction_method": "Table_Transformer_Enhanced"
            }
            
            # 4. 시각화 생성 (선택사항)
            visualization_files = []
            if create_visualization and enhanced_tables:
                try:
                    from utils.table_visualizer import visualize_table_detection_quick
                    
                    viz_output_dir = output_dir if output_dir else "temp_visualization"
                    viz_result = visualize_table_detection_quick(pdf_path, enhanced_tables, viz_output_dir)
                    
                    if viz_result["success"]:
                        visualization_files = viz_result["image_files"]
                        final_result["visualization"] = {
                            "image_files": visualization_files,
                            "html_report": viz_result["html_report"],
                            "output_dir": viz_result["output_dir"]
                        }
                        self.logger.info(f"시각화 생성 완료: {len(visualization_files)}개 이미지")
                    else:
                        self.logger.warning(f"시각화 생성 실패: {viz_result.get('error', 'Unknown')}")
                        
                except ImportError:
                    self.logger.warning("시각화 모듈을 찾을 수 없습니다. matplotlib 설치 필요")
                except Exception as e:
                    self.logger.warning(f"시각화 생성 중 오류: {str(e)}")
            
            # 5. 결과 저장 (선택사항)
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                
                output_file = output_path / f"{Path(pdf_path).stem}_table_transformer.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"결과 저장: {output_file}")
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Table Transformer PDF 처리 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tables": []
            }

# 사용 예시 및 테스트 함수
def test_table_transformer():
    """Table Transformer 테스트"""
    
    if not TRANSFORMER_AVAILABLE:
        print("❌ Table Transformer 라이브러리가 설치되지 않았습니다.")
        return
    
    try:
        detector = TableTransformerDetector()
        
        # 테스트용 PDF 경로 (실제 파일로 교체 필요)
        test_pdf = "test_document.pdf"
        
        if Path(test_pdf).exists():
            result = detector.process_pdf_with_table_transformer(test_pdf)
            
            print("🎯 Table Transformer 결과:")
            print(f"   성공: {result['success']}")
            print(f"   감지된 표: {result.get('total_tables', 0)}개")
            
            if result["tables"]:
                print(f"   첫 번째 표:")
                first_table = result["tables"][0]
                print(f"     페이지: {first_table['page_number']}")
                print(f"     신뢰도: {first_table['confidence_score']:.2%}")
                print(f"     크기: {first_table['bbox']['width']:.0f}x{first_table['bbox']['height']:.0f}")
        else:
            print(f"❌ 테스트 파일이 없습니다: {test_pdf}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    test_table_transformer() 