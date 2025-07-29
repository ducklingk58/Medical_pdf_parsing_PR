# 🎯 사용자 정의 JSON 스키마 가이드

## 📋 개요

이 시스템은 사용자가 제공한 **배열 형태의 JSON 스키마**에 맞춰서 PDF 처리 결과를 출력합니다. 기존의 복잡한 구조화된 JSON 대신, 사용자가 원하는 간단하고 명확한 형태로 데이터를 제공합니다.

## 🏗️ 사용자 정의 JSON 스키마

### 📊 스키마 구조

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "id": {
        "type": "string",
        "description": "고유 식별자 (UUID)"
      },
      "text": {
        "type": "string", 
        "description": "추출된 텍스트 내용"
      },
      "metadata": {
        "type": "object",
        "properties": {
          "page": {
            "type": "integer",
            "description": "페이지 번호"
          },
          "type": {
            "type": "string",
            "description": "콘텐츠 타입 (paragraph, title, table, etc.)"
          },
          "document_order": {
            "type": "integer",
            "description": "문서 내 순서"
          },
          "content_length": {
            "type": "integer",
            "description": "텍스트 길이"
          },
          "has_table": {
            "type": "boolean",
            "description": "표 포함 여부"
          },
          "section_title": {
            "type": "string",
            "description": "소속 섹션 제목"
          },
          "preprocessed": {
            "type": "boolean",
            "description": "전처리 완료 여부"
          }
        },
        "required": [
          "page", "type", "document_order", "content_length", 
          "has_table", "section_title", "preprocessed"
        ]
      }
    },
    "required": ["id", "text", "metadata"]
  }
}
```

### 🎯 출력 예시

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "이 문서는 의약품의 시판 후 정기적인 안전성정보 보고를 위한 지침입니다.",
    "metadata": {
      "page": 1,
      "type": "paragraph",
      "document_order": 1,
      "content_length": 42,
      "has_table": false,
      "section_title": "개요",
      "preprocessed": true
    }
  },
  {
    "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "text": "표 1. 안전성 검토 항목\n항목 | 검토 기준 | 완료 여부\n중요한 규명된 위해성 | 위해성 완화조치 실시 | 완료\n중요한 잠재적 위해성 | 추가 연구 실시 | 진행 중",
    "metadata": {
      "page": 2,
      "type": "table",
      "document_order": 2,
      "content_length": 89,
      "has_table": true,
      "section_title": "검토 방법",
      "preprocessed": true
    }
  },
  {
    "id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    "text": "1. 목적",
    "metadata": {
      "page": 1,
      "type": "title",
      "document_order": 3,
      "content_length": 6,
      "has_table": false,
      "section_title": "목적",
      "preprocessed": true
    }
  }
]
```

## 🚀 사용 방법

### 1. 기본 사용법

```bash
# 단일 PDF 처리 (사용자 스키마 JSON 자동 생성)
python Medical_pdf_processor_enhanced.py

# 또는 테스트 스크립트 실행
python test_user_schema.py
```

### 2. 배치 처리

```bash
# 여러 PDF 파일 동시 처리
python run_processing.py --input ./input_pdfs --output ./output_data
```

### 3. 대시보드 사용

```bash
# Streamlit 대시보드 실행
python dashboard/app.py
```

## 📁 출력 파일 구조

PDF 처리 후 다음과 같은 파일들이 생성됩니다:

```
output_data/
├── {pdf_filename}/
│   ├── user_schema_output.json       # 🎯 사용자 정의 스키마 JSON
│   ├── structured_document.json      # 기존 구조화된 JSON
│   ├── enhanced_metadata.json        # 메타데이터
│   ├── enhanced_summary.json         # 처리 요약
│   ├── enhanced_markdown.md          # 마크다운 파일
│   ├── tables/                       # 추출된 표 파일들
│   └── images/                       # 추출된 이미지들
```

### 🎯 핵심 파일: `user_schema_output.json`

이 파일이 사용자가 요청한 스키마 형태로 생성되는 **메인 출력 파일**입니다.

## 📊 메타데이터 필드 설명

### `type` 필드 값들

- **`paragraph`**: 일반 문단 텍스트
- **`title`**: 문서 제목
- **`heading`**: 섹션 헤딩
- **`section_title`**: 섹션 제목
- **`table`**: 표 데이터
- **`list`**: 목록 항목
- **`text`**: 기타 텍스트

### `has_table` 필드

- **`true`**: 해당 텍스트에 표 관련 내용이 포함됨
- **`false`**: 순수 텍스트만 포함됨

### `preprocessed` 필드

- **`true`**: 텍스트 정제, 연결, 청킹 등의 전처리가 완료됨
- **`false`**: 원본 텍스트 그대로 (오류 상황에서만 발생)

## 🧪 테스트 및 검증

### 1. 스키마 테스트

```bash
# 테스트 스크립트 실행
python test_user_schema.py
```

테스트 스크립트는 다음을 수행합니다:
- PDF 파일 처리
- 사용자 스키마 JSON 생성
- 스키마 형식 검증
- 결과 미리보기

### 2. 스키마 검증 항목

- ✅ 배열 형태 구조
- ✅ 필수 필드 존재 (`id`, `text`, `metadata`)
- ✅ 메타데이터 필수 필드 존재
- ✅ 데이터 타입 일치성
- ✅ UUID 형태의 고유 ID

## 🔧 고급 사용법

### 1. 커스텀 처리

```python
from utils.user_schema_generator import create_user_schema_json

# 텍스트 청크와 표 데이터로부터 사용자 스키마 JSON 생성
user_schema_json = create_user_schema_json(
    text_chunks=your_text_chunks,
    extracted_tables=your_tables,
    source_file="example.pdf"
)

# JSON 파일로 저장
import json
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(user_schema_json, f, ensure_ascii=False, indent=2)
```

### 2. 스키마 커스터마이징

`utils/user_schema_generator.py` 파일을 수정하여 다음을 변경할 수 있습니다:

- 타입 결정 로직 (`_determine_chunk_type`)
- 섹션 제목 인식 (`_is_section_title`)
- 표 감지 로직 (`_check_has_table`)
- 전처리 규칙

## 🚨 주의사항

### 1. 파일 크기

- 대용량 PDF 파일의 경우 처리 시간이 길어질 수 있습니다
- JSON 파일 크기가 클 수 있으니 메모리 사용량을 고려하세요

### 2. 한국어 지원

- 모든 텍스트는 UTF-8로 인코딩됩니다
- 한국어 의료 문서에 최적화되어 있습니다

### 3. 표 처리

- 복잡한 표 구조는 텍스트로 변환되어 저장됩니다
- 원본 표 구조는 별도 `tables/` 디렉토리에 보존됩니다

## 🎉 완성된 기능

✅ **사용자 정의 스키마 JSON 생성**  
✅ **배열 형태 구조 출력**  
✅ **UUID 기반 고유 ID**  
✅ **상세한 메타데이터**  
✅ **텍스트/표 통합 처리**  
✅ **스키마 검증 기능**  
✅ **테스트 스크립트 제공**  

이제 PDF를 넣으면 사용자가 요청한 JSON 스키마 형태로 정확히 출력됩니다! 🎯 