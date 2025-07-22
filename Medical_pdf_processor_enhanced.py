"""
향상된 Medical PDF 처리기
기존 Unstructured 텍스트 파싱 + LayoutParser/PaddleOCR 고급 테이블/이미지 파싱
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# 기존 모듈 imports
from utils.pdf_processor import PDFProcessor
from utils.logger import setup_logger
from config.settings import Settings

# 고급 파싱 모듈 import
from utils.simple_advanced_parser import SimpleAdvancedParser

class EnhancedPDFProcessor(PDFProcessor):
    """향상된 PDF 처리기 - 기존 텍스트 파싱 + 고급 테이블/이미지 파싱"""
    
    def __init__(self, use_gpu: bool = False, similarity_threshold: float = 0.7):
        super().__init__()
        self.use_gpu = use_gpu
        self.similarity_threshold = similarity_threshold
        
        # 고급 파싱기 초기화
        self.advanced_parser = SimpleAdvancedParser(use_gpu=use_gpu)
        
        self.logger.info(f"향상된 PDF 처리기 초기화 완료 (GPU: {use_gpu})")
    
    def process_pdf_enhanced(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """향상된 PDF 처리 파이프라인"""
        start_time = time.time()
        
        try:
            self.logger.info(f"향상된 PDF 처리 시작: {pdf_path}")
            
            # 출력 디렉토리 설정
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 원본 파일명 추출
            original_filename = Path(pdf_path).stem
            
            # 1. 기존 Unstructured 텍스트 파싱 (유지)
            self.logger.info("1단계: Unstructured 텍스트 파싱")
            elements = self.partition_pdf_text_only(pdf_path)
            text_elements = self.extract_text_elements(elements)
            
            # 2. 고급 파싱 (간단한 테이블/이미지 파싱)
            self.logger.info("2단계: 간단한 테이블/이미지 파싱")
            advanced_result = self.advanced_parser.process_pdf_simple(pdf_path, str(output_path))
            
            # 3. 텍스트 정제 및 문장 연결 (기존 로직 유지)
            self.logger.info("3단계: 텍스트 정제 및 문장 연결")
            connected_blocks = self.connect_sentences(text_elements)
            
            # 4. RAG 청킹 (기존 로직 유지)
            self.logger.info("4단계: RAG 청킹")
            rag_chunks = self.create_rag_chunks(connected_blocks)
            
            # 5. 고급 테이블/이미지 저장 (파일명 규칙 준수)
            self.logger.info("5단계: 고급 테이블/이미지 저장")
            table_files = self.save_advanced_tables(advanced_result["tables"], 
                                                   output_path, original_filename)
            image_files = self.save_advanced_images(advanced_result["images"], 
                                                   output_path, original_filename)
            
            # 6. 향상된 마크다운 생성
            self.logger.info("6단계: 향상된 마크다운 생성")
            md_file = self.create_enhanced_markdown(rag_chunks, table_files, 
                                                   image_files, output_path, original_filename)
            
            # 7. 향상된 메타데이터 생성
            self.logger.info("7단계: 향상된 메타데이터 생성")
            enhanced_metadata = self.create_enhanced_metadata(
                original_filename, rag_chunks, table_files, image_files, advanced_result
            )
            
            # 메타데이터 저장
            metadata_path = output_path / "enhanced_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(enhanced_metadata, f, ensure_ascii=False, indent=2, default=str)
            
            # 8. 요약 생성
            self.logger.info("8단계: 요약 생성")
            processing_time = time.time() - start_time
            summary = {
                'original_file_name': original_filename,
                'processing_time': processing_time,
                'statistics': {
                    'text_chunks_count': len(rag_chunks),
                    'table_files_count': len(table_files),
                    'image_files_count': len(image_files),
                    'total_pages': advanced_result.get("total_pages", 1)
                },
                'files': {
                    'markdown': str(md_file),
                    'metadata': str(metadata_path),
                    'tables': table_files,
                    'images': image_files
                },
                'processing_method': 'EnhancedPDFProcessor',
                'gpu_used': self.use_gpu
            }
            
            summary_path = output_path / "enhanced_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"향상된 PDF 처리 완료: {processing_time:.2f}초")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"향상된 PDF 처리 실패: {str(e)}")
            raise
    
    def save_advanced_tables(self, extracted_tables: List[Dict], output_dir: Path, 
                           original_filename: str) -> List[str]:
        """고급 파싱으로 추출된 테이블 저장 (파일명 규칙 준수)"""
        table_files = []
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        for i, table in enumerate(extracted_tables):
            table_id = f"{original_filename}_table_{i+1:03d}"
            page_num = table.get("element_info", {}).get("page_num", 1)
            
            # JSON 형태로 저장
            json_path = tables_dir / f"{table_id}_page_{page_num}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2, default=str)
            
            # CSV 형태로도 저장 (DataFrame이 있는 경우)
            if "dataframe" in table and table["dataframe"] is not None:
                csv_path = tables_dir / f"{table_id}_page_{page_num}.csv"
                table["dataframe"].to_csv(csv_path, index=False, encoding='utf-8-sig')
                table_files.append(str(csv_path))
            
            # Excel 형태로도 저장
            if "dataframe" in table and table["dataframe"] is not None:
                excel_path = tables_dir / f"{table_id}_page_{page_num}.xlsx"
                table["dataframe"].to_excel(excel_path, index=False, engine='openpyxl')
            
            # HTML 형태로도 저장
            if "html" in table:
                html_path = tables_dir / f"{table_id}_page_{page_num}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(table["html"])
        
        self.logger.info(f"고급 테이블 데이터 저장 완료: {len(table_files)}개 파일")
        return table_files
    
    def save_advanced_images(self, extracted_images: List[Dict], output_dir: Path,
                           original_filename: str) -> List[str]:
        """고급 파싱으로 추출된 이미지 저장 (파일명 규칙 준수)"""
        image_files = []
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        for i, image in enumerate(extracted_images):
            image_id = f"{original_filename}_image_{i+1:03d}"
            page_num = image.get("page_num", 1)
            
            # 이미지 파일 저장
            if "image_bytes" in image:
                image_path = images_dir / f"{image_id}_page_{page_num}.{image['format']}"
                with open(image_path, 'wb') as f:
                    f.write(image["image_bytes"])
                image_files.append(str(image_path))
            
            # 메타데이터 JSON 저장
            metadata_path = images_dir / f"{image_id}_page_{page_num}_metadata.json"
            metadata = {k: v for k, v in image.items() if k != "image_bytes"}
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
        
        self.logger.info(f"고급 이미지 데이터 저장 완료: {len(image_files)}개 파일")
        return image_files
    
    def create_enhanced_markdown(self, text_blocks: List[Dict[str, Any]], 
                               table_files: List[str], image_files: List[str], 
                               output_dir: Path, original_filename: str) -> str:
        """향상된 마크다운 파일 생성"""
        md_content = []
        
        # 문서 제목
        md_content.append(f"# {original_filename}\n\n")
        
        # 텍스트 블록 추가
        for i, block in enumerate(text_blocks):
            if block["type"] == "Title":
                md_content.append(f"## {block['text']}\n\n")
            else:
                md_content.append(f"{block['text']}\n\n")
        
        # 고급 테이블 참조 추가
        if table_files:
            md_content.append("## 추출된 테이블 (고급 파싱)\n")
            for table_file in table_files:
                table_name = Path(table_file).stem
                table_dir = Path(table_file).parent
                
                # CSV 파일 링크
                md_content.append(f"- [테이블 데이터 (CSV): {table_name}]({table_file})\n")
                
                # Excel 파일이 있으면 링크 추가
                excel_file = table_dir / f"{table_name}.xlsx"
                if excel_file.exists():
                    md_content.append(f"- [테이블 데이터 (Excel): {table_name}]({excel_file})\n")
                
                # HTML 파일이 있으면 링크 추가
                html_file = table_dir / f"{table_name}.html"
                if html_file.exists():
                    md_content.append(f"- [테이블 데이터 (HTML): {table_name}]({html_file})\n")
            md_content.append("\n")
        
        # 고급 이미지 참조 추가
        if image_files:
            md_content.append("## 추출된 이미지 (고급 파싱)\n")
            for image_file in image_files:
                image_name = Path(image_file).stem
                image_dir = Path(image_file).parent
                
                # 이미지 파일 링크
                md_content.append(f"- ![이미지: {image_name}]({image_file})\n")
                
                # 메타데이터 파일이 있으면 링크 추가
                metadata_file = image_dir / f"{image_name}_metadata.json"
                if metadata_file.exists():
                    md_content.append(f"- [이미지 메타데이터: {image_name}]({metadata_file})\n")
            md_content.append("\n")
        
        # 향상된 마크다운 파일 저장
        md_path = output_dir / f"{original_filename}_enhanced.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.writelines(md_content)
        
        self.logger.info(f"향상된 마크다운 파일 생성 완료: {md_path}")
        return str(md_path)
    
    def create_enhanced_metadata(self, original_filename: str, text_chunks: List[Dict[str, Any]], 
                               table_files: List[str], image_files: List[str], 
                               advanced_result: Dict[str, Any]) -> Dict[str, Any]:
        """향상된 메타데이터 생성"""
        enhanced_metadata = {
            'file_info': {
                'original_filename': original_filename,
                'processing_method': 'EnhancedPDFProcessor',
                'gpu_used': self.use_gpu,
                'processing_timestamp': time.time()
            },
            'statistics': {
                'text_chunks_count': len(text_chunks),
                'table_files_count': len(table_files),
                'image_files_count': len(image_files),
                'total_pages': advanced_result.get("total_pages", 1)
            },
            'text_chunks': text_chunks,
            'tables': {
                'files': table_files,
                'raw_data': advanced_result.get("tables", [])
            },
            'images': {
                'files': image_files,
                'raw_data': advanced_result.get("images", [])
            },
            'advanced_parsing_info': {
                'extraction_method': advanced_result.get("processing_method", "Unknown"),
                'layout_analysis': True,
                'ocr_enhanced': True
            }
        }
        
        return enhanced_metadata
    
    def cleanup(self):
        """리소스 정리"""
        if hasattr(self, 'advanced_parser'):
            self.advanced_parser.cleanup()
    
    def __del__(self):
        """소멸자에서 정리"""
        self.cleanup() 