#!/usr/bin/env python3
"""
Medical PDF 파싱 프로젝트 메인 실행 스크립트
Medical_pdf_parsing_PR

이 스크립트는 500개의 의료 PDF 파일을 Unstructured를 활용하여 고급 파싱하는 시스템입니다.
"""

import sys
import argparse
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from main_processor import BatchPDFProcessor
from config.settings import Settings
from utils.logger import setup_logger
from utils.validation import export_validation_report, check_file_integrity

def main():
    """메인 실행 함수"""
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(
        description="Medical PDF 파싱 프로젝트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_processing.py                    # 기본 설정으로 실행
  python run_processing.py --input ./pdfs     # 입력 디렉토리 지정
  python run_processing.py --workers 8        # 워커 수 지정
  python run_processing.py --validate-only    # 검증만 실행
  python run_processing.py --dashboard        # 대시보드 실행
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
        "--validate-only",
        action="store_true",
        help="파싱 없이 검증만 실행"
    )
    
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Streamlit 대시보드 실행"
    )
    
    parser.add_argument(
        "--check-integrity",
        action="store_true",
        help="파일 무결성 검사 실행"
    )
    
    parser.add_argument(
        "--create-report",
        action="store_true",
        help="검증 보고서 생성"
    )
    
    args = parser.parse_args()
    
    # 로거 설정
    logger = setup_logger()
    
    # 설정 디렉토리 생성
    Settings.create_directories()
    
    logger.info("=" * 80)
    logger.info("🏥 Medical PDF 파싱 프로젝트 시작")
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
                    sys.executable, "-m", "streamlit", "run", str(dashboard_path)
                ], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"대시보드 실행 오류: {e}")
                sys.exit(1)
        else:
            logger.error(f"대시보드 파일을 찾을 수 없습니다: {dashboard_path}")
            sys.exit(1)
        return
    
    # 입력 디렉토리 확인
    input_dir = args.input or str(Settings.INPUT_DIR)
    output_dir = args.output or str(Settings.OUTPUT_DIR)
    
    logger.info(f"📁 입력 디렉토리: {input_dir}")
    logger.info(f"📁 출력 디렉토리: {output_dir}")
    
    # 입력 디렉토리 존재 확인
    if not Path(input_dir).exists():
        logger.error(f"입력 디렉토리가 존재하지 않습니다: {input_dir}")
        logger.info("PDF 파일을 input_pdfs 디렉토리에 복사한 후 다시 실행하세요.")
        sys.exit(1)
    
    # PDF 파일 확인
    pdf_files = list(Path(input_dir).glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"입력 디렉토리에 PDF 파일이 없습니다: {input_dir}")
        logger.info("PDF 파일을 입력 디렉토리에 복사한 후 다시 실행하세요.")
        sys.exit(1)
    
    logger.info(f"📄 발견된 PDF 파일 수: {len(pdf_files)}")
    
    # 검증만 실행
    if args.validate_only:
        logger.info("🔍 검증 모드 실행...")
        
        if not Path(output_dir).exists():
            logger.error(f"출력 디렉토리가 존재하지 않습니다: {output_dir}")
            logger.info("먼저 파싱을 실행한 후 검증을 수행하세요.")
            sys.exit(1)
        
        # 검증 보고서 생성
        if args.create_report:
            logger.info("📊 검증 보고서 생성 중...")
            report = export_validation_report(output_dir)
            logger.info(f"검증 보고서 생성 완료: {output_dir}/validation_report.json")
        
        # 무결성 검사
        if args.check_integrity:
            logger.info("🔍 파일 무결성 검사 중...")
            integrity_results = check_file_integrity(output_dir)
            logger.info(f"무결성 검사 완료: {integrity_results['complete_directories']}/{integrity_results['total_directories']} 완전")
        
        logger.info("✅ 검증 완료")
        return
    
    # 배치 프로세서 초기화
    max_workers = args.workers or Settings.MAX_WORKERS
    processor = BatchPDFProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        max_workers=max_workers
    )
    
    # 처리 실행
    try:
        logger.info("🚀 PDF 파싱 시작...")
        summary = processor.process_all_pdfs()
        
        logger.info("✅ 파싱 완료!")
        logger.info(f"📊 결과 요약:")
        logger.info(f"   총 파일: {summary['total_files']}")
        logger.info(f"   성공: {summary['successful_files']}")
        logger.info(f"   실패: {summary['failed_files']}")
        logger.info(f"   성공률: {summary['success_rate']:.2%}")
        logger.info(f"   총 처리 시간: {summary['total_processing_time']:.2f}초")
        
        # 검증 보고서 생성
        if args.create_report or summary['successful_files'] > 0:
            logger.info("📊 검증 보고서 생성 중...")
            try:
                report = export_validation_report(output_dir)
                logger.info(f"검증 보고서 생성 완료: {output_dir}/validation_report.json")
            except Exception as e:
                logger.warning(f"검증 보고서 생성 실패: {str(e)}")
        
        # 무결성 검사
        if args.check_integrity:
            logger.info("🔍 파일 무결성 검사 중...")
            try:
                integrity_results = check_file_integrity(output_dir)
                logger.info(f"무결성 검사 완료: {integrity_results['complete_directories']}/{integrity_results['total_directories']} 완전")
            except Exception as e:
                logger.warning(f"무결성 검사 실패: {str(e)}")
        
        # 실패한 파일 목록 출력
        failed_files = [r for r in summary['results'] if r['status'] == 'error']
        if failed_files:
            logger.warning("❌ 실패한 파일들:")
            for failed in failed_files:
                logger.warning(f"   - {failed['filename']}: {failed['error']}")
        
        # 성공한 파일들의 상세 통계
        successful_results = [r for r in summary['results'] if r['status'] == 'success']
        if successful_results:
            total_text_blocks = sum(r['summary'].get('text_blocks_count', 0) for r in successful_results)
            total_tables = sum(r['summary'].get('tables_count', 0) for r in successful_results)
            total_images = sum(r['summary'].get('images_count', 0) for r in successful_results)
            total_chunks = sum(r['summary'].get('rag_chunks_count', 0) for r in successful_results)
            
            logger.info("📈 추출 결과:")
            logger.info(f"   총 텍스트 블록: {total_text_blocks:,}")
            logger.info(f"   총 표: {total_tables:,}")
            logger.info(f"   총 이미지: {total_images:,}")
            logger.info(f"   총 RAG 청크: {total_chunks:,}")
        
        logger.info("=" * 80)
        logger.info("🎉 Medical PDF 파싱 프로젝트 완료!")
        logger.info("=" * 80)
        
        # 대시보드 실행 안내
        logger.info("💡 대시보드를 실행하려면: python run_processing.py --dashboard")
        
    except KeyboardInterrupt:
        logger.info("⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 처리 중 오류 발생: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 