# 🏥 Medical PDF 파싱 프로젝트 (Medical_pdf_parsing_PR)

Unstructured 라이브러리를 활용한 대량 의료 PDF 고급 파싱 시스템

## 📋 프로젝트 개요

이 프로젝트는 500개의 의료 제품 관련 PDF 파일을 Unstructured 라이브러리를 활용하여 고급 파싱 및 후처리하는 시스템입니다. 텍스트 추출, 표 구조화, 이미지 처리, 문장 연결, RAG 친화적 청킹을 포함한 종합적인 PDF 처리 파이프라인을 제공합니다.

## ✨ 주요 기능

### 🔧 핵심 파싱 기능
- **Unstructured 기반 고급 파싱**: PDF에서 텍스트, 표, 이미지 추출
- **의미론적 문장 연결**: sentence-transformers를 활용한 지능형 텍스트 재구성
- **구조화된 표 처리**: pandas DataFrame으로 즉시 변환
- **RAG 친화적 청킹**: 검색 시스템 최적화된 텍스트 분할

### 🚀 처리 성능
- **병렬 처리**: ThreadPoolExecutor로 대량 파일 효율 처리
- **진행률 모니터링**: tqdm을 활용한 실시간 진행 상황 표시
- **오류 관리**: 파일별 오류 로그와 중앙 집중식 로깅 시스템

### 📊 모니터링 및 시각화
- **Streamlit 대시보드**: 실시간 처리 현황 시각화
- **품질 검증**: 자동화된 결과 검증 및 보고서 생성
- **통계 분석**: 상세한 처리 통계 및 품질 지표

## 🏗️ 프로젝트 구조

```
Medical_pdf_parsing_PR/
├── input_pdfs/                    # 입력 PDF 파일들 (500개)
├── output_data/                   # 파싱 결과 저장
│   ├── {filename_without_ext}/    # 각 PDF별 결과 디렉토리
│   │   ├── text/                  # 정제된 텍스트 파일들
│   │   ├── tables/                # 추출된 표 데이터
│   │   ├── images/                # 추출된 이미지들
│   │   ├── metadata/              # 메타데이터 JSON 파일들
│   │   ├── summary.json           # 파싱 요약 정보
│   │   └── final_markdown.md      # 최종 마크다운 파일
├── logs/                          # 로그 파일들
│   ├── processing.log             # 전체 처리 로그
│   └── error_{filename}.txt       # 파일별 오류 로그
├── config/                        # 설정 파일들
│   └── settings.py                # 프로젝트 설정
├── utils/                         # 유틸리티 함수들
│   ├── pdf_processor.py           # PDF 처리기
│   ├── logger.py                  # 로깅 시스템
│   └── validation.py              # 검증 유틸리티
├── dashboard/                     # 시각화 대시보드
│   └── app.py                     # Streamlit 대시보드
├── main_processor.py              # 배치 처리기
├── run_processing.py              # 메인 실행 스크립트
├── requirements.txt               # 의존성 목록
└── README.md                      # 프로젝트 문서
```

## 🚀 설치 및 설정

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
conda create -n medical_pdf_parsing python=3.11
conda activate medical_pdf_parsing

# 또는 venv 사용
python -m venv medical_pdf_parsing_env
# Windows
medical_pdf_parsing_env\Scripts\activate
# Linux/Mac
source medical_pdf_parsing_env/bin/activate
```

### 2. 의존성 설치

```bash
# 프로젝트 디렉토리로 이동
cd Medical_pdf_parsing_PR

# 의존성 설치
pip install -r requirements.txt
```

### 3. PDF 파일 준비

```bash
# input_pdfs 디렉토리에 PDF 파일들을 복사
cp /path/to/your/pdfs/*.pdf input_pdfs/
```

## 📖 사용 방법

### 기본 실행

```bash
# 기본 설정으로 모든 PDF 파일 처리
python run_processing.py
```

### 고급 옵션

```bash
# 입력/출력 디렉토리 지정
python run_processing.py --input ./my_pdfs --output ./my_results

# 병렬 처리 워커 수 지정
python run_processing.py --workers 8

# 검증만 실행
python run_processing.py --validate-only

# 검증 보고서 생성
python run_processing.py --create-report

# 파일 무결성 검사
python run_processing.py --check-integrity

# Streamlit 대시보드 실행
python run_processing.py --dashboard
```

### 대시보드 실행

```bash
# 별도로 대시보드 실행
streamlit run dashboard/app.py
```

## 🔧 설정 옵션

`config/settings.py`에서 다음 설정을 조정할 수 있습니다:

```python
# 처리 설정
MAX_WORKERS = 4                    # 병렬 처리 워커 수
SIMILARITY_THRESHOLD = 0.7         # 문장 연결 유사도 임계값
CHUNK_SIZE = 512                   # RAG 청크 크기
CHUNK_OVERLAP = 50                 # 청크 중복 크기

# PDF 처리 설정
PDF_EXTRACT_IMAGES = True          # 이미지 추출 활성화
PDF_EXTRACT_TABLES = True          # 표 추출 활성화
INCLUDE_IMAGE_METADATA = True      # 이미지 메타데이터 포함

# 텍스트 정제 설정
REMOVE_PAGE_NUMBERS = True         # 페이지 번호 제거
REMOVE_HEADERS_FOOTERS = True      # 헤더/푸터 제거
```

## 📊 출력 결과

### 개별 PDF 결과 구조

각 PDF 파일별로 다음과 같은 결과가 생성됩니다:

```
output_data/{filename}/
├── summary.json              # 파싱 요약 정보
├── metadata.json             # 상세 메타데이터
├── final_markdown.md         # 최종 마크다운 파일
├── tables/                   # 추출된 표 데이터
│   ├── table_001.json       # JSON 형태
│   ├── table_001.csv        # CSV 형태
│   └── ...
└── images/                   # 이미지 메타데이터
    ├── image_001.json
    └── ...
```

### 배치 처리 결과

```
output_data/
├── batch_summary.json        # 전체 배치 처리 요약
├── validation_report.json    # 검증 보고서
├── validation_report.xlsx    # Excel 형태 검증 보고서
└── logs/                     # 로그 파일들
    ├── processing_*.log      # 처리 로그
    ├── errors_*.log          # 오류 로그
    └── error_{filename}.txt  # 파일별 오류 로그
```

## 🔍 품질 검증

### 자동 검증 기능

- **텍스트 블록 검증**: 텍스트 추출 성공 여부 확인
- **표 데이터 검증**: 구조화된 데이터 변환 확인
- **RAG 청크 검증**: 청킹 프로세스 확인
- **파일 무결성 검사**: 필수 파일 존재 여부 확인

### 품질 지표

- **품질 점수**: 0-1 범위의 종합 품질 평가
- **평균 처리 시간**: 파일당 평균 처리 시간
- **성공률**: 전체 처리 성공률
- **이상치 탐지**: 비정상적인 결과 자동 탐지

## 📈 대시보드 기능

### 실시간 모니터링

- **처리 진행률**: 실시간 진행 상황 시각화
- **성공/실패 통계**: 처리 결과 분포 차트
- **품질 지표**: 다양한 품질 메트릭 표시

### 상세 분석

- **파일별 상세 정보**: 개별 파일 처리 결과
- **통계 차트**: 텍스트 블록, 표, 이미지 분포
- **이상치 탐지**: 문제가 있는 파일 자동 식별

## 🛠️ 고급 기능

### 의미론적 문장 연결

sentence-transformers를 활용하여 논리적으로 연결된 텍스트 블록을 생성합니다:

```python
# 유사도 기반 문장 연결
similarity = calculate_similarity(text1, text2)
if similarity >= threshold:
    # 문장 연결
    connected_text = text1 + "\n\n" + text2
```

### 구조화된 표 처리

Unstructured의 `text_as_csv`를 pandas DataFrame으로 즉시 변환:

```python
# CSV 형태로 구조화
df = pd.read_csv(io.StringIO(element.metadata.text_as_csv))
table_data["structured_data"] = df.to_dict('records')
```

### RAG 친화적 청킹

검색 시스템에 최적화된 텍스트 청킹:

```python
# 중복을 포함한 청킹
for i in range(0, len(words), chunk_size - overlap):
    chunk_words = words[i:i + chunk_size]
    chunks.append({
        "text": ' '.join(chunk_words),
        "word_count": len(chunk_words),
        "token_estimate": len(chunk_words) * 1.3
    })
```

## 🔧 문제 해결

### 일반적인 문제

1. **메모리 부족**
   - `MAX_WORKERS` 수를 줄이세요
   - `CHUNK_SIZE`를 줄이세요

2. **처리 속도 개선**
   - `MAX_WORKERS` 수를 늘리세요
   - GPU 가속을 활용하세요

3. **품질 개선**
   - `SIMILARITY_THRESHOLD`를 조정하세요
   - 텍스트 정제 패턴을 추가하세요

### 로그 확인

```bash
# 처리 로그 확인
tail -f logs/processing_*.log

# 오류 로그 확인
tail -f logs/errors_*.log

# 특정 파일 오류 확인
cat logs/error_{filename}.txt
```

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 기여

버그 리포트, 기능 요청, 풀 리퀘스트를 환영합니다.

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. 로그 파일 확인
2. 설정 파일 검토
3. 의존성 버전 확인
4. GitHub Issues 등록

---

**Medical_pdf_parsing_PR** - 의료 PDF 고급 파싱 시스템 