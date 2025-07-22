import os
import logging
import traceback
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import json
import time

from utils.pdf_processor import PDFProcessor
from utils.logger import setup_logger, log_processing_start, log_processing_end, log_file_processing
from config.settings import Settings

class BatchPDFProcessor:
    """대량 PDF 파일 배치 처리기"""
    
    def __init__(self, input_dir: str = None, output_dir: str = None, max_workers: int = None):
        self.input_dir = Path(input_dir) if input_dir else Settings.INPUT_DIR
        self.output_dir = Path(output_dir) if output_dir else Settings.OUTPUT_DIR
        self.max_workers = max_workers or Settings.MAX_WORKERS
        self.logger = setup_logger()
        self.processor = PDFProcessor()
        
        # 디렉토리 생성
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)
        
        self.logger.info(f"배치 프로세서 초기화 완료")
        self.logger.info(f"입력 디렉토리: {self.input_dir}")
        self.logger.info(f"출력 디렉토리: {self.output_dir}")
        self.logger.info(f"최대 워커 수: {self.max_workers}")
    
    def get_pdf_files(self) -> List[Path]:
        """입력 디렉토리에서 모든 PDF 파일 경로 수집"""
        pdf_files = []
        
        # 지원하는 확장자로 파일 검색
        for ext in Settings.SUPPORTED_EXTENSIONS:
            pdf_files.extend(list(self.input_dir.rglob(f"*{ext}")))
        
        # 중복 제거 및 정렬
        pdf_files = sorted(list(set(pdf_files)))
        
        self.logger.info(f"총 {len(pdf_files)}개의 PDF 파일을 발견했습니다.")
        
        # 파일 존재 여부 확인
        valid_files = [f for f in pdf_files if f.exists() and f.is_file()]
        if len(valid_files) != len(pdf_files):
            self.logger.warning(f"일부 파일이 존재하지 않습니다: {len(pdf_files) - len(valid_files)}개")
        
        return valid_files
    
    def process_single_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """단일 PDF 파일 처리"""
        result = {
            "filename": pdf_path.name,
            "filepath": str(pdf_path),
            "status": "success",
            "error": None,
            "summary": {},
            "processing_time": 0,
            "timestamp": time.time()
        }
        
        start_time = time.time()
        
        try:
            # 파일별 로거 생성
            file_logger = self.logger
            
            # 출력 디렉토리 설정
            output_subdir = self.output_dir / pdf_path.stem
            
            # 개별 PDF 처리
            summary = self.processor.process_pdf(
                pdf_path=str(pdf_path),
                output_dir=str(output_subdir)
            )
            
            result["summary"] = summary
            result["processing_time"] = time.time() - start_time
            
            # 성공 로깅
            log_file_processing(
                file_logger, 
                pdf_path.name, 
                "success", 
                f"처리 시간: {result['processing_time']:.2f}초, "
                f"텍스트 블록: {summary.get('text_blocks_count', 0)}, "
                f"표: {summary.get('tables_count', 0)}, "
                f"이미지: {summary.get('images_count', 0)}"
            )
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            
            # 파일별 오류 로그 저장
            error_log_path = self.output_dir / "logs" / f"error_{pdf_path.stem}.txt"
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(f"파일: {pdf_path.name}\n")
                f.write(f"경로: {pdf_path}\n")
                f.write(f"오류: {str(e)}\n")
                f.write(f"처리 시간: {result['processing_time']:.2f}초\n")
                f.write(f"상세 정보:\n{traceback.format_exc()}\n")
            
            # 오류 로깅
            log_file_processing(
                self.logger, 
                pdf_path.name, 
                "error", 
                f"처리 시간: {result['processing_time']:.2f}초", 
                str(e)
            )
        
        return result
    
    def process_all_pdfs(self) -> Dict[str, Any]:
        """모든 PDF 파일 배치 처리"""
        pdf_files = self.get_pdf_files()
        
        if not pdf_files:
            self.logger.warning("처리할 PDF 파일이 없습니다.")
            return {
                "total_files": 0,
                "successful_files": 0,
                "failed_files": 0,
                "success_rate": 0.0,
                "results": [],
                "total_processing_time": 0,
                "average_processing_time": 0
            }
        
        # 처리 시작 로깅
        log_processing_start(self.logger, len(pdf_files))
        
        results = []
        start_time = time.time()
        
        # 병렬 처리 또는 순차 처리
        if self.max_workers > 1:
            self.logger.info(f"병렬 처리 시작 (워커 수: {self.max_workers})")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 작업 제출
                future_to_pdf = {
                    executor.submit(self.process_single_pdf, pdf_path): pdf_path 
                    for pdf_path in pdf_files
                }
                
                # 결과 수집
                for future in tqdm(as_completed(future_to_pdf), 
                                 total=len(pdf_files), 
                                 desc="PDF 처리 진행률",
                                 unit="파일"):
                    pdf_path = future_to_pdf[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"Future 처리 중 오류: {pdf_path.name} - {str(e)}")
                        # 오류 결과 추가
                        results.append({
                            "filename": pdf_path.name,
                            "filepath": str(pdf_path),
                            "status": "error",
                            "error": f"Future 처리 오류: {str(e)}",
                            "summary": {},
                            "processing_time": 0,
                            "timestamp": time.time()
                        })
        else:
            self.logger.info("순차 처리 시작")
            
            # 순차 처리
            for pdf_path in tqdm(pdf_files, desc="PDF 처리 진행률", unit="파일"):
                result = self.process_single_pdf(pdf_path)
                results.append(result)
        
        # 전체 처리 시간 계산
        total_processing_time = time.time() - start_time
        
        # 결과 분석
        total_files = len(results)
        successful_files = len([r for r in results if r["status"] == "success"])
        failed_files = total_files - successful_files
        success_rate = successful_files / total_files if total_files > 0 else 0
        
        # 평균 처리 시간 계산
        processing_times = [r["processing_time"] for r in results if r["processing_time"] > 0]
        average_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        # 전체 요약 생성
        summary = {
            "total_files": total_files,
            "successful_files": successful_files,
            "failed_files": failed_files,
            "success_rate": success_rate,
            "total_processing_time": total_processing_time,
            "average_processing_time": average_processing_time,
            "results": results,
            "processing_info": {
                "max_workers": self.max_workers,
                "input_directory": str(self.input_dir),
                "output_directory": str(self.output_dir),
                "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            }
        }
        
        # 전체 요약 저장
        summary_path = self.output_dir / "batch_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 처리 완료 로깅
        log_processing_end(self.logger, summary)
        
        # 상세 통계 출력
        self._print_detailed_statistics(summary)
        
        return summary
    
    def _print_detailed_statistics(self, summary: Dict[str, Any]):
        """상세 통계 출력"""
        self.logger.info("=" * 60)
        self.logger.info("상세 처리 통계")
        self.logger.info("=" * 60)
        
        # 기본 통계
        self.logger.info(f"총 파일 수: {summary['total_files']}")
        self.logger.info(f"성공한 파일 수: {summary['successful_files']}")
        self.logger.info(f"실패한 파일 수: {summary['failed_files']}")
        self.logger.info(f"성공률: {summary['success_rate']:.2%}")
        
        # 시간 통계
        self.logger.info(f"총 처리 시간: {summary['total_processing_time']:.2f}초")
        self.logger.info(f"평균 처리 시간: {summary['average_processing_time']:.2f}초/파일")
        
        # 성공한 파일들의 상세 통계
        successful_results = [r for r in summary['results'] if r['status'] == 'success']
        if successful_results:
            total_text_blocks = sum(r['summary'].get('text_blocks_count', 0) for r in successful_results)
            total_tables = sum(r['summary'].get('tables_count', 0) for r in successful_results)
            total_images = sum(r['summary'].get('images_count', 0) for r in successful_results)
            total_chunks = sum(r['summary'].get('rag_chunks_count', 0) for r in successful_results)
            
            self.logger.info(f"총 추출된 텍스트 블록: {total_text_blocks}")
            self.logger.info(f"총 추출된 표: {total_tables}")
            self.logger.info(f"총 추출된 이미지: {total_images}")
            self.logger.info(f"총 생성된 RAG 청크: {total_chunks}")
        
        # 실패한 파일 목록
        failed_results = [r for r in summary['results'] if r['status'] == 'error']
        if failed_results:
            self.logger.warning("실패한 파일 목록:")
            for failed in failed_results:
                self.logger.warning(f"  - {failed['filename']}: {failed['error']}")
        
        self.logger.info("=" * 60)

if __name__ == "__main__":
    # 설정 디렉토리 생성
    Settings.create_directories()
    
    # 배치 프로세서 실행
    processor = BatchPDFProcessor()
    summary = processor.process_all_pdfs()
    
    print(f"\n처리 완료!")
    print(f"성공: {summary['successful_files']}/{summary['total_files']}")
    print(f"성공률: {summary['success_rate']:.2%}")
    print(f"총 처리 시간: {summary['total_processing_time']:.2f}초") 