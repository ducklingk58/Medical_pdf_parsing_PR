#!/usr/bin/env python3
"""
향상된 Medical PDF 파싱 프로젝트 실행 스크립트
기존 Unstructured 텍스트 파싱 + LayoutParser/PaddleOCR 고급 테이블/이미지 파싱
"""

import sys
import argparse
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from Medical_pdf_processor_enhanced import EnhancedPDFProcessor
from config.settings import Settings
from utils.logger import setup_logger

def main():
    """메인 실행 함수"""
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(
        description="향상된 Medical PDF 파싱 프로젝트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_enhanced_processing.py                    # 기본 설정으로 실행
  python run_enhanced_processing.py --input ./pdfs     # 입력 디렉토리 지정
  python run_enhanced_processing.py --workers 8        # 워커 수 지정
  python run_enhanced_processing.py --use-gpu          # GPU 가속 사용
  python run_enhanced_processing.py --dashboard        # 대시보드 실행
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="입력 PDF 디렉토리 경로 (기본값: input_pdfs)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="출력 디렉토리 경로 (기본값: output_data)"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        help="병렬 처리 워커 수 (기본값: 4)"
    )
    
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="GPU 가속 사용"
    )
    
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Streamlit 대시보드 실행"
    )
    
    args = parser.parse_args()
    
    # 로거 설정
    logger = setup_logger()
    
    # 설정 디렉토리 생성
    Settings.create_directories()
    
    logger.info("=" * 80)
    logger.info("🚀 향상된 Medical PDF 파싱 프로젝트 시작")
    logger.info("=" * 80)
    
    # 대시보드 실행
    if args.dashboard:
        logger.info("📊 Streamlit 대시보드 실행 중...")
        import subprocess
        import os
        
        dashboard_path = project_root / "dashboard" / "app.py"
        if dashboard_path.exists():
            try:
                subprocess.run([
                    sys.executable, "-m", "streamlit", "run", 
                    str(dashboard_path),
                    "--server.port", "8501"
                ])
            except KeyboardInterrupt:
                logger.info("대시보드가 중단되었습니다.")
        else:
            logger.error("대시보드 파일을 찾을 수 없습니다.")
        return
    
    # 입력/출력 디렉토리 설정
    input_dir = Path(args.input) if args.input else Settings.INPUT_DIR
    output_dir = Path(args.output) if args.output else Settings.OUTPUT_DIR
    max_workers = args.workers or Settings.MAX_WORKERS
    
    # GPU 사용 여부
    use_gpu = args.use_gpu
    
    logger.info(f"입력 디렉토리: {input_dir}")
    logger.info(f"출력 디렉토리: {output_dir}")
    logger.info(f"최대 워커 수: {max_workers}")
    logger.info(f"GPU 사용: {use_gpu}")
    
    # PDF 파일 목록 가져오기
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"입력 디렉토리에서 PDF 파일을 찾을 수 없습니다: {input_dir}")
        return
    
    logger.info(f"처리할 PDF 파일: {len(pdf_files)}개")
    
    # 향상된 PDF 처리기 초기화
    processor = EnhancedPDFProcessor(use_gpu=use_gpu)
    
    # 배치 처리 결과 저장용
    results = []
    successful_files = 0
    failed_files = 0
    
    start_time = time.time()
    
    try:
        # 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_file = {
                executor.submit(process_single_pdf, processor, pdf_file, output_dir): pdf_file
                for pdf_file in pdf_files
            }
            
            # 진행률 표시
            with tqdm(total=len(pdf_files), desc="PDF 처리 중") as pbar:
                for future in as_completed(future_to_file):
                    pdf_file = future_to_file[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        successful_files += 1
                        logger.info(f"✅ 성공: {pdf_file.name}")
                    except Exception as e:
                        failed_files += 1
                        logger.error(f"❌ 실패: {pdf_file.name} - {str(e)}")
                    
                    pbar.update(1)
    
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    finally:
        # 리소스 정리
        processor.cleanup()
    
    # 처리 시간 계산
    total_time = time.time() - start_time
    
    # 배치 처리 요약 생성
    batch_summary = {
        'total_files': len(pdf_files),
        'successful_files': successful_files,
        'failed_files': failed_files,
        'success_rate': successful_files / len(pdf_files) if pdf_files else 0,
        'total_processing_time': total_time,
        'average_processing_time': total_time / len(pdf_files) if pdf_files else 0,
        'results': results,
        'processing_method': 'EnhancedPDFProcessor',
        'gpu_used': use_gpu
    }
    
    # 배치 요약 저장
    batch_summary_path = output_dir / "enhanced_batch_summary.json"
    import json
    with open(batch_summary_path, 'w', encoding='utf-8') as f:
        json.dump(batch_summary, f, ensure_ascii=False, indent=2, default=str)
    
    # 결과 출력
    logger.info("=" * 80)
    logger.info("🎉 향상된 배치 처리 완료!")
    logger.info("=" * 80)
    logger.info(f"총 파일 수: {len(pdf_files)}")
    logger.info(f"성공한 파일 수: {successful_files}")
    logger.info(f"실패한 파일 수: {failed_files}")
    logger.info(f"성공률: {batch_summary['success_rate']:.2%}")
    logger.info(f"총 처리 시간: {total_time:.2f}초")
    logger.info(f"평균 처리 시간: {batch_summary['average_processing_time']:.2f}초")
    logger.info(f"배치 요약 저장: {batch_summary_path}")

def process_single_pdf(processor: EnhancedPDFProcessor, pdf_file: Path, output_dir: Path) -> dict:
    """단일 PDF 파일 처리"""
    try:
        # 출력 디렉토리 생성
        output_path = output_dir / pdf_file.stem
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 향상된 PDF 처리
        summary = processor.process_pdf_enhanced(str(pdf_file), str(output_path))
        
        return {
            'filename': pdf_file.name,
            'status': 'success',
            'processing_time': summary.get('processing_time', 0),
            'statistics': summary.get('statistics', {}),
            'output_path': str(output_path)
        }
        
    except Exception as e:
        return {
            'filename': pdf_file.name,
            'status': 'failed',
            'error': str(e),
            'processing_time': 0
        }

if __name__ == "__main__":
    main() 