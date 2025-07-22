import logging
import sys
from pathlib import Path
from datetime import datetime
from config.settings import Settings

def setup_logger(name: str = "medical_pdf_parser", 
                log_level: str | None = None,
                log_dir: str | None = None) -> logging.Logger:
    """로깅 시스템 설정"""
    
    # 설정에서 기본값 가져오기
    if log_level is None:
        log_level = Settings.LOG_LEVEL
    if log_dir is None:
        log_dir = Settings.LOG_DIR
    
    # 로그 디렉토리 생성
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (전체 로그)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_handler = logging.FileHandler(
        log_path / f"processing_{timestamp}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # 에러 전용 파일 핸들러
    error_handler = logging.FileHandler(
        log_path / f"errors_{timestamp}.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)
    
    return logger

def create_file_logger(filename: str, log_dir: str | None = None) -> logging.Logger:
    """특정 파일 전용 로거 생성 (파일별 오류 로깅용)"""
    if log_dir is None:
        log_dir = Settings.LOG_DIR
    
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 파일명에서 확장자 제거
    clean_filename = Path(filename).stem
    
    # 파일별 로거 생성
    logger = logging.getLogger(f"file_{clean_filename}")
    logger.setLevel(logging.ERROR)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 파일별 오류 로그 핸들러
    error_file_handler = logging.FileHandler(
        log_path / f"error_{clean_filename}.txt",
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s\n'
    )
    error_file_handler.setFormatter(error_format)
    logger.addHandler(error_file_handler)
    
    return logger

def log_processing_start(logger: logging.Logger, total_files: int):
    """처리 시작 로깅"""
    logger.info("=" * 60)
    logger.info("Medical PDF 파싱 프로젝트 시작")
    logger.info(f"총 처리할 파일 수: {total_files}")
    logger.info(f"입력 디렉토리: {Settings.INPUT_DIR}")
    logger.info(f"출력 디렉토리: {Settings.OUTPUT_DIR}")
    logger.info(f"최대 워커 수: {Settings.MAX_WORKERS}")
    logger.info("=" * 60)

def log_processing_end(logger: logging.Logger, summary: dict):
    """처리 완료 로깅"""
    logger.info("=" * 60)
    logger.info("Medical PDF 파싱 프로젝트 완료")
    logger.info(f"총 파일: {summary.get('total_files', 0)}")
    logger.info(f"성공: {summary.get('successful_files', 0)}")
    logger.info(f"실패: {summary.get('failed_files', 0)}")
    logger.info(f"성공률: {summary.get('success_rate', 0):.2%}")
    logger.info("=" * 60)

def log_file_processing(logger: logging.Logger, filename: str, status: str, 
                       details: str | None = None, error: str | None = None):
    """개별 파일 처리 로깅"""
    if status == "success":
        logger.info(f"✅ {filename}: 처리 완료")
        if details:
            logger.debug(f"   상세: {details}")
    elif status == "error":
        logger.error(f"❌ {filename}: 처리 실패 - {error}")
        if details:
            logger.debug(f"   상세: {details}")
    else:
        logger.warning(f"⚠️ {filename}: {status}")
        if details:
            logger.debug(f"   상세: {details}") 