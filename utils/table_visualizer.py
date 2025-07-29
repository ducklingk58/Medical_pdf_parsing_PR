#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Table Transformer 감지 결과 시각화 모듈
Table Detection Visualization Module
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import numpy as np
from typing import List, Dict, Any, Tuple
import logging
from pathlib import Path
import io

class TableVisualizationHelper:
    """Table Transformer 감지 결과 시각화"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def visualize_table_detection(self, pdf_path: str, detection_results: List[Dict], output_dir: str = None) -> List[str]:
        """
        Table Transformer 감지 결과를 시각화
        
        Args:
            pdf_path: PDF 파일 경로
            detection_results: Table Transformer 감지 결과
            output_dir: 출력 디렉토리 (None이면 임시 디렉토리)
            
        Returns:
            생성된 이미지 파일 경로들
        """
        try:
            self.logger.info(f"표 감지 결과 시각화 시작: {len(detection_results)}개 표")
            
            if not detection_results:
                self.logger.warning("시각화할 표 감지 결과가 없습니다.")
                return []
            
            # PDF를 이미지로 변환
            doc = fitz.open(pdf_path)
            image_files = []
            
            # 페이지별로 그룹화
            pages_with_tables = {}
            for table in detection_results:
                page_num = table.get('page_number', 1)
                if page_num not in pages_with_tables:
                    pages_with_tables[page_num] = []
                pages_with_tables[page_num].append(table)
            
            # 출력 디렉토리 설정
            if output_dir is None:
                output_dir = Path("temp_visualization")
            else:
                output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 각 페이지별로 시각화
            for page_num, tables in pages_with_tables.items():
                try:
                    # PDF 페이지를 이미지로 변환
                    page = doc.load_page(page_num - 1)
                    mat = fitz.Matrix(2.0, 2.0)  # 2배 확대
                    pix = page.get_pixmap(matrix=mat)
                    
                    # PIL Image로 변환
                    img_data = pix.tobytes("ppm")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # 표 영역 그리기
                    img_with_boxes = self._draw_table_boxes(img, tables, page_num)
                    
                    # 상세 정보 추가
                    img_with_info = self._add_detection_info(img_with_boxes, tables, page_num)
                    
                    # 이미지 저장
                    output_file = output_dir / f"page_{page_num}_table_detection.png"
                    img_with_info.save(output_file, "PNG", quality=95)
                    image_files.append(str(output_file))
                    
                    self.logger.info(f"페이지 {page_num} 시각화 완료: {output_file}")
                    
                except Exception as e:
                    self.logger.error(f"페이지 {page_num} 시각화 실패: {str(e)}")
                    continue
            
            doc.close()
            
            # 요약 이미지 생성
            if len(image_files) > 0:
                summary_file = self._create_summary_image(image_files, detection_results, output_dir)
                if summary_file:
                    image_files.insert(0, summary_file)
            
            self.logger.info(f"총 {len(image_files)}개 시각화 이미지 생성 완료")
            return image_files
            
        except Exception as e:
            self.logger.error(f"표 감지 시각화 실패: {str(e)}")
            return []
    
    def _draw_table_boxes(self, img: Image, tables: List[Dict], page_num: int) -> Image:
        """이미지에 표 영역 박스 그리기"""
        try:
            # 이미지 복사
            img_copy = img.copy()
            draw = ImageDraw.Draw(img_copy)
            
            # 색상 설정 (신뢰도별로 다른 색상)
            colors = [
                (255, 0, 0),    # 빨강 (높은 신뢰도)
                (255, 165, 0),  # 주황 (중간 신뢰도)
                (255, 255, 0),  # 노랑 (낮은 신뢰도)
            ]
            
            for i, table in enumerate(tables):
                bbox = table.get('bbox', {})
                confidence = table.get('confidence_score', 0.0)
                
                if bbox:
                    # 박스 좌표 (PDF 좌표계를 이미지 좌표계로 변환)
                    x1 = int(bbox.get('x', 0) * 2)  # 2배 확대 적용
                    y1 = int(bbox.get('y', 0) * 2)
                    x2 = int((bbox.get('x', 0) + bbox.get('width', 100)) * 2)
                    y2 = int((bbox.get('y', 0) + bbox.get('height', 100)) * 2)
                    
                    # 신뢰도에 따른 색상 선택
                    if confidence >= 0.8:
                        color = colors[0]  # 빨강
                    elif confidence >= 0.6:
                        color = colors[1]  # 주황
                    else:
                        color = colors[2]  # 노랑
                    
                    # 박스 그리기
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
                    
                    # 표 번호와 신뢰도 표시
                    label = f"T{i+1}: {confidence:.2%}"
                    
                    # 라벨 배경 그리기
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    
                    bbox_text = draw.textbbox((0, 0), label, font=font)
                    text_width = bbox_text[2] - bbox_text[0]
                    text_height = bbox_text[3] - bbox_text[1]
                    
                    # 라벨 배경
                    draw.rectangle([x1, y1-text_height-5, x1+text_width+10, y1], fill=color)
                    
                    # 라벨 텍스트
                    draw.text((x1+5, y1-text_height-2), label, fill=(255, 255, 255), font=font)
            
            return img_copy
            
        except Exception as e:
            self.logger.error(f"표 박스 그리기 실패: {str(e)}")
            return img
    
    def _add_detection_info(self, img: Image, tables: List[Dict], page_num: int) -> Image:
        """감지 정보 텍스트 추가"""
        try:
            draw = ImageDraw.Draw(img)
            
            # 폰트 설정
            try:
                title_font = ImageFont.truetype("arial.ttf", 24)
                info_font = ImageFont.truetype("arial.ttf", 16)
            except:
                title_font = ImageFont.load_default()
                info_font = ImageFont.load_default()
            
            # 정보 텍스트 생성
            info_lines = [
                f"페이지 {page_num} - Table Transformer 감지 결과",
                f"감지된 표: {len(tables)}개",
                "",
                "표별 상세 정보:"
            ]
            
            for i, table in enumerate(tables):
                confidence = table.get('confidence_score', 0.0)
                bbox = table.get('bbox', {})
                width = bbox.get('width', 0)
                height = bbox.get('height', 0)
                
                info_lines.append(f"  T{i+1}: 신뢰도 {confidence:.2%}, 크기 {width:.0f}x{height:.0f}")
            
            # 정보 패널 배경
            panel_width = 400
            panel_height = len(info_lines) * 25 + 20
            panel_x = img.width - panel_width - 10
            panel_y = 10
            
            # 반투명 배경
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle([panel_x, panel_y, panel_x + panel_width, panel_y + panel_height], 
                                 fill=(0, 0, 0, 180))
            
            # 원본 이미지와 오버레이 합성
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(img)
            
            # 텍스트 그리기
            y_offset = panel_y + 10
            for i, line in enumerate(info_lines):
                if i == 0:  # 제목
                    draw.text((panel_x + 10, y_offset), line, fill=(255, 255, 255), font=title_font)
                    y_offset += 30
                else:
                    draw.text((panel_x + 10, y_offset), line, fill=(255, 255, 255), font=info_font)
                    y_offset += 20
            
            return img
            
        except Exception as e:
            self.logger.error(f"감지 정보 추가 실패: {str(e)}")
            return img
    
    def _create_summary_image(self, image_files: List[str], detection_results: List[Dict], output_dir: Path) -> str:
        """전체 요약 이미지 생성"""
        try:
            # matplotlib을 사용한 요약 차트
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # 1. 페이지별 표 개수
            page_counts = {}
            confidence_scores = []
            
            for table in detection_results:
                page_num = table.get('page_number', 1)
                page_counts[page_num] = page_counts.get(page_num, 0) + 1
                confidence_scores.append(table.get('confidence_score', 0.0))
            
            # 페이지별 표 개수 막대 차트
            pages = list(page_counts.keys())
            counts = list(page_counts.values())
            
            ax1.bar(pages, counts, color='skyblue', alpha=0.7)
            ax1.set_xlabel('페이지 번호')
            ax1.set_ylabel('감지된 표 개수')
            ax1.set_title('페이지별 표 감지 개수')
            ax1.grid(True, alpha=0.3)
            
            # 2. 신뢰도 분포 히스토그램
            ax2.hist(confidence_scores, bins=10, color='lightcoral', alpha=0.7, edgecolor='black')
            ax2.set_xlabel('신뢰도')
            ax2.set_ylabel('표 개수')
            ax2.set_title('Table Transformer 신뢰도 분포')
            ax2.grid(True, alpha=0.3)
            
            # 통계 정보 추가
            avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
            fig.suptitle(f'Table Transformer 감지 요약 (총 {len(detection_results)}개, 평균 신뢰도: {avg_confidence:.2%})', 
                        fontsize=16, fontweight='bold')
            
            plt.tight_layout()
            
            # 저장
            summary_file = output_dir / "table_detection_summary.png"
            plt.savefig(summary_file, dpi=150, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"요약 이미지 생성: {summary_file}")
            return str(summary_file)
            
        except Exception as e:
            self.logger.error(f"요약 이미지 생성 실패: {str(e)}")
            return None
    
    def create_interactive_html_report(self, pdf_path: str, detection_results: List[Dict], 
                                     image_files: List[str], output_dir: str = None) -> str:
        """인터랙티브 HTML 보고서 생성"""
        try:
            if output_dir is None:
                output_dir = Path("temp_visualization")
            else:
                output_dir = Path(output_dir)
            
            # HTML 템플릿
            html_content = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Table Transformer 감지 결과</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                    .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
                    .summary {{ background-color: white; padding: 15px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .image-container {{ text-align: center; margin: 20px 0; }}
                    .image-container img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px; }}
                    .table-info {{ background-color: #ecf0f1; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                    .confidence-high {{ color: #27ae60; font-weight: bold; }}
                    .confidence-medium {{ color: #f39c12; font-weight: bold; }}
                    .confidence-low {{ color: #e74c3c; font-weight: bold; }}
                    .navigation {{ background-color: white; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                    .navigation a {{ margin: 0 10px; text-decoration: none; color: #3498db; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🤖 Microsoft Table Transformer 감지 결과</h1>
                    <p>PDF: {Path(pdf_path).name}</p>
                </div>
                
                <div class="summary">
                    <h2>📊 감지 요약</h2>
                    <ul>
                        <li><strong>총 감지된 표:</strong> {len(detection_results)}개</li>
                        <li><strong>평균 신뢰도:</strong> {np.mean([t.get('confidence_score', 0) for t in detection_results]):.2%}</li>
                        <li><strong>최고 신뢰도:</strong> {max([t.get('confidence_score', 0) for t in detection_results]) if detection_results else 0:.2%}</li>
                        <li><strong>최저 신뢰도:</strong> {min([t.get('confidence_score', 0) for t in detection_results]) if detection_results else 0:.2%}</li>
                    </ul>
                </div>
                
                <div class="navigation">
                    <h3>📋 페이지 네비게이션</h3>
            """
            
            # 페이지별 네비게이션 링크
            pages = sorted(set(t.get('page_number', 1) for t in detection_results))
            for page in pages:
                html_content += f'<a href="#page_{page}">페이지 {page}</a>'
            
            html_content += """
                </div>
            """
            
            # 각 표별 상세 정보
            for i, table in enumerate(detection_results):
                confidence = table.get('confidence_score', 0.0)
                page_num = table.get('page_number', 1)
                
                # 신뢰도에 따른 클래스
                if confidence >= 0.8:
                    conf_class = "confidence-high"
                elif confidence >= 0.6:
                    conf_class = "confidence-medium"
                else:
                    conf_class = "confidence-low"
                
                html_content += f"""
                <div id="page_{page_num}" class="table-info">
                    <h3>표 {i+1} (페이지 {page_num})</h3>
                    <ul>
                        <li><strong>신뢰도:</strong> <span class="{conf_class}">{confidence:.2%}</span></li>
                        <li><strong>위치:</strong> ({table.get('bbox', {}).get('x', 0):.0f}, {table.get('bbox', {}).get('y', 0):.0f})</li>
                        <li><strong>크기:</strong> {table.get('bbox', {}).get('width', 0):.0f} × {table.get('bbox', {}).get('height', 0):.0f}</li>
                        <li><strong>추출된 텍스트:</strong> {table.get('extracted_text', 'N/A')[:100]}{'...' if len(table.get('extracted_text', '')) > 100 else ''}</li>
                    </ul>
                </div>
                """
            
            # 이미지들 추가
            for img_file in image_files:
                img_name = Path(img_file).name
                html_content += f"""
                <div class="image-container">
                    <h3>{img_name}</h3>
                    <img src="{img_name}" alt="{img_name}">
                </div>
                """
            
            html_content += """
            </body>
            </html>
            """
            
            # HTML 파일 저장
            html_file = output_dir / "table_detection_report.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"HTML 보고서 생성: {html_file}")
            return str(html_file)
            
        except Exception as e:
            self.logger.error(f"HTML 보고서 생성 실패: {str(e)}")
            return None

# 편의 함수
def visualize_table_detection_quick(pdf_path: str, detection_results: List[Dict], output_dir: str = None) -> Dict[str, Any]:
    """빠른 표 감지 결과 시각화"""
    try:
        visualizer = TableVisualizationHelper()
        
        # 이미지 생성
        image_files = visualizer.visualize_table_detection(pdf_path, detection_results, output_dir)
        
        # HTML 보고서 생성
        html_file = visualizer.create_interactive_html_report(pdf_path, detection_results, image_files, output_dir)
        
        return {
            "success": True,
            "image_files": image_files,
            "html_report": html_file,
            "total_tables": len(detection_results),
            "output_dir": output_dir
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        } 