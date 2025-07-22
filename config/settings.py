import os
from pathlib import Path

class Settings:
    """Medical PDF 파싱 프로젝트 설정"""
    
    # 기본 경로
    BASE_DIR = Path(__file__).parent.parent
    INPUT_DIR = BASE_DIR / "input_pdfs"
    OUTPUT_DIR = BASE_DIR / "output_data"
    LOG_DIR = BASE_DIR / "logs"
    
    # 처리 설정
    MAX_WORKERS = 4  # 병렬 처리 워커 수 (CPU 코어 수에 따라 조정)
    SIMILARITY_THRESHOLD = 0.7  # 문장 연결 유사도 임계값
    CHUNK_SIZE = 512  # RAG 청크 크기 (토큰 기준)
    CHUNK_OVERLAP = 50  # 청크 중복 크기
    
    # 로깅 설정
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 모델 설정
    SENTENCE_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers 모델
    
    # PDF 처리 설정
    PDF_EXTRACT_IMAGES = True
    PDF_EXTRACT_TABLES = True
    INCLUDE_IMAGE_METADATA = True
    
    # 텍스트 정제 설정
    REMOVE_PAGE_NUMBERS = True
    REMOVE_HEADERS_FOOTERS = True
    
    # 파일 확장자
    SUPPORTED_EXTENSIONS = ['.pdf']
    
    # 출력 파일 설정
    SAVE_AS_JSON = True
    SAVE_AS_CSV = True
    SAVE_AS_MARKDOWN = True
    
    @classmethod
    def create_directories(cls):
        """필요한 디렉토리 생성"""
        directories = [
            cls.INPUT_DIR,
            cls.OUTPUT_DIR,
            cls.LOG_DIR,
            cls.BASE_DIR / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
            print(f"디렉토리 생성/확인: {directory}")
    
    @classmethod
    def get_output_subdirs(cls, filename: str) -> dict:
        """PDF 파일별 출력 서브디렉토리 경로 반환"""
        base_dir = cls.OUTPUT_DIR / filename
        return {
            "base": base_dir,
            "text": base_dir / "text",
            "tables": base_dir / "tables",
            "images": base_dir / "images",
            "metadata": base_dir / "metadata"
        }
    
    @classmethod
    def validate_environment(cls):
        """환경 설정 검증"""
        # 필수 디렉토리 확인
        if not cls.INPUT_DIR.exists():
            print(f"경고: 입력 디렉토리가 존재하지 않습니다: {cls.INPUT_DIR}")
        
        # PDF 파일 확인
        pdf_files = list(cls.INPUT_DIR.glob("*.pdf"))
        print(f"발견된 PDF 파일 수: {len(pdf_files)}")
        
        return len(pdf_files) > 0 