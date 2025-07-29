# 📋 **JSON 출력 스키마 가이드**

## 🏗️ **구조화된 문서 스키마**

이제 PDF 파싱 결과가 **사용자 정의 구조화된 JSON 형태**로 출력됩니다! `text_blocks`는 완전히 제외되고, 대신 의미있는 섹션과 표 구조로 조직화됩니다.

---

## 📊 **새로운 구조화된 스키마**

### **🏛️ 최상위 구조**
```json
{
  "document_title": "문서 제목",
  "version": "버전 정보",
  "summary": "문서 요약",
  "sections": [...],
  "tables": [...],
  "metadata": {...}
}
```

### **📖 섹션 구조 (`sections`)**
```json
{
  "title": "개요",
  "type": "text",  // 섹션 제목의 타입 (text/table)
  "subsections": [
    {
      "title": "목적",
      "type": "text",  // 하위 섹션 제목의 타입
      "content": "본 지침은 의약품의 RMP 및 재심사 시 정기적 안전성정보 보고를 위한 실무 지침이다.",
      "content_types": ["text", "table"]  // 내용에 포함된 타입들 (혼합된 경우)
    },
    {
      "title": "관련 규정 요약", 
      "type": "text",
      "content": "의약품 등의 안전에 관한 규칙, 품목허가 심사규정, 재심사 기준 등",
      "content_types": ["text"]  // 순수 텍스트만 포함
    }
  ]
}
```

### **📊 표 구조 (`tables`)**
```json
{
  "title": "RMP 이행 현황 요약표",
  "type": "table",  // 표는 항상 "table" 타입
  "headers": ["안전성중점검토항목", "위해성 완화 조치방법", "실시 상황"],
  "rows": [
    ["중요한 규명된 위해성", "위해성 완화조치 실시", "이행 완료"],
    ["중요한 잠재적 위해성", "추가 연구 실시", "진행 중"]
  ],
  "metadata": {
    "page_number": 3,
    "extraction_tool": "Microsoft_Table_Transformer",
    "confidence_score": 0.85
  }
}
```

### **🔍 타입 필드 설명**

#### **섹션 타입 (`sections[].type`)**
- **`"text"`**: 일반 텍스트에서 추출된 섹션 제목
- **`"table"`**: 표에서 추출된 섹션 제목 (드물지만 가능)

#### **하위 섹션 타입 (`sections[].subsections[].type`)**  
- **`"text"`**: 일반 텍스트에서 추출된 하위 섹션 제목
- **`"table"`**: 표에서 추출된 하위 섹션 제목

#### **내용 타입 배열 (`content_types`)**
- **`["text"]`**: 순수 텍스트만 포함
- **`["table"]`**: 표 데이터만 포함
- **`["text", "table"]`**: 텍스트와 표 데이터가 혼합됨

#### **표 타입 (`tables[].type`)**
- **`"table"`**: 모든 표는 항상 "table" 타입

---

## 🎯 **실제 JSON 출력 예시**

```json
{
  "document_title": "의약품의 시판 후 정기적인 안전성정보 보고 검토지침",
  "version": "2021.02",
  "summary": "이 문서는 RMP 및 재심사 상황에서 정기적인 안전성 보고 및 검토 절차를 안내하는 공무원 지침서입니다.",
  "sections": [
    {
      "title": "개요",
      "type": "text",
      "subsections": [
        {
          "title": "목적",
          "type": "text",
          "content": "본 지침은 의약품의 RMP 및 재심사 시 정기적 안전성정보 보고를 위한 실무 지침이다.",
          "content_types": ["text"]
        },
        {
          "title": "관련 규정 요약",
          "type": "text",
          "content": "의약품 등의 안전에 관한 규칙, 품목허가 심사규정, 재심사 기준 등",
          "content_types": ["text"]
        }
      ]
    },
    {
      "title": "적용 범위",
      "type": "text",
      "subsections": [
        {
          "title": "RMP 보고",
          "type": "text",
          "content": "위해성 관리계획 이행 및 PSUR 제출 대상",
          "content_types": ["text"]
        },
        {
          "title": "재심사 보고", 
          "type": "text",
          "content": "시판 후 조사 정기보고서 작성 대상",
          "content_types": ["text"]
        }
      ]
    }
  ],
  "tables": [
    {
      "title": "RMP 이행 현황 요약표",
      "type": "table",
      "headers": ["안전성중점검토항목", "위해성 완화 조치방법", "실시 상황"],
      "rows": [
        ["중요한 규명된 위해성", "위해성 완화조치 실시", "이행 완료"],
        ["중요한 잠재적 위해성", "추가 연구 실시", "진행 중"]
      ],
      "metadata": {
        "page_number": 3,
        "extraction_tool": "Microsoft_Table_Transformer",
        "confidence_score": 0.85
      }
    },
    {
      "title": "정기보고서 제출 이행 사항",
      "type": "table",
      "headers": ["년차", "1-1년차", "1-2년차", "2-1년차", "누계"],
      "rows": [
        ["보고일", "2021.03.15", "2021.09.15", "2022.03.15", "3회"]
      ],
      "metadata": {
        "page_number": 5,
        "extraction_tool": "Microsoft_Table_Transformer", 
        "confidence_score": 0.92
      }
    }
  ],
  "metadata": {
    "source_file": "의약품_안전성정보_지침.pdf",
    "processing_date": "2025-01-24",
    "total_sections": 2,
    "total_tables": 2,
    "document_type": "지침서"
  }
}
```

### 🚫 **제외된 항목들**
- ❌ **`text_blocks`**: 더 이상 출력에 포함되지 않음
- ❌ **`rag_chunks`**: 대신 구조화된 sections로 대체
- ❌ **복잡한 청크 메타데이터**: 간소화된 구조

---

## 🔍 **활용 방법**

### **🔍 전체 문서 검색**
```python
def search_document(data, keyword):
    """전체 문서에서 키워드 검색"""
    results = []
    
    # 섹션에서 검색
    for section in data["sections"]:
        if keyword.lower() in section["title"].lower():
            results.append(f"Section: {section['title']} (type: {section.get('type', 'unknown')})")
        
        for subsection in section.get("subsections", []):
            if keyword.lower() in subsection["content"].lower():
                content_types = subsection.get("content_types", ["unknown"])
                results.append(f"Content: {section['title']} > {subsection['title']} (content_types: {content_types})")
    
    # 표에서 검색
    for table in data["tables"]:
        if keyword.lower() in table["title"].lower():
            results.append(f"Table: {table['title']} (type: {table.get('type', 'table')})")
            
        # 표 내용에서 검색
        for row in table["rows"]:
            if any(keyword.lower() in str(cell).lower() for cell in row):
                results.append(f"Table Data: {table['title']} (type: table)")
                break
    
    return results

def filter_by_type(data, target_type):
    """특정 타입의 데이터만 필터링"""
    filtered_data = {
        "sections": [],
        "tables": []
    }
    
    # 섹션 필터링
    for section in data["sections"]:
        if section.get("type") == target_type:
            filtered_data["sections"].append(section)
        else:
            # 하위 섹션에서 특정 타입 내용 찾기
            filtered_subsections = []
            for subsection in section.get("subsections", []):
                content_types = subsection.get("content_types", [])
                if target_type in content_types:
                    filtered_subsections.append(subsection)
            
            if filtered_subsections:
                filtered_section = section.copy()
                filtered_section["subsections"] = filtered_subsections
                filtered_data["sections"].append(filtered_section)
    
    # 표 필터링
    if target_type == "table":
        filtered_data["tables"] = data["tables"]
    
    return filtered_data

def get_content_statistics(data):
    """타입별 내용 통계"""
    stats = {
        "sections": {
            "total": len(data["sections"]),
            "text_type": 0,
            "table_type": 0
        },
        "subsections": {
            "total": 0,
            "text_type": 0,
            "table_type": 0,
            "mixed_content": 0,
            "pure_text": 0,
            "pure_table": 0
        },
        "tables": {
            "total": len(data["tables"])
        }
    }
    
    for section in data["sections"]:
        # 섹션 타입 통계
        section_type = section.get("type", "text")
        if section_type == "text":
            stats["sections"]["text_type"] += 1
        elif section_type == "table":
            stats["sections"]["table_type"] += 1
        
        # 하위 섹션 통계
        for subsection in section.get("subsections", []):
            stats["subsections"]["total"] += 1
            
            subsection_type = subsection.get("type", "text")
            if subsection_type == "text":
                stats["subsections"]["text_type"] += 1
            elif subsection_type == "table":
                stats["subsections"]["table_type"] += 1
            
            # 내용 타입 통계
            content_types = subsection.get("content_types", ["text"])
            if len(content_types) > 1:
                stats["subsections"]["mixed_content"] += 1
            elif "text" in content_types:
                stats["subsections"]["pure_text"] += 1
            elif "table" in content_types:
                stats["subsections"]["pure_table"] += 1
    
    return stats

# 사용 예시
search_results = search_document(data, "안전성")
text_only_data = filter_by_type(data, "text")
table_only_data = filter_by_type(data, "table")
content_stats = get_content_statistics(data)

print(f"순수 텍스트 섹션: {content_stats['subsections']['pure_text']}개")
print(f"표 데이터 포함 섹션: {content_stats['subsections']['pure_table']}개") 
print(f"혼합 내용 섹션: {content_stats['subsections']['mixed_content']}개")
```

---

## 📈 **메타데이터 정보**

새로운 구조화된 JSON의 `metadata`에서 제공되는 정보:

- **`source_file`**: 원본 PDF 파일명
- **`processing_date`**: 처리 날짜
- **`total_sections`**: 전체 섹션 개수
- **`total_tables`**: 전체 표 개수
- **`document_type`**: 문서 타입 (지침서, 규정집, 보고서 등)

---

## ✅ **새로운 구조의 장점들!**

1. **📖 의미있는 구조화**: 섹션별로 논리적으로 조직화된 문서
2. **📊 명확한 표 데이터**: 헤더와 행으로 구조화된 표 정보
3. **🚫 불필요한 정보 제거**: `text_blocks` 등 중복 데이터 제거
4. **🔍 효율적인 검색**: 섹션별, 표별 타겟 검색 가능
5. **📋 사용자 친화적**: 직관적이고 읽기 쉬운 JSON 구조
6. **🎯 RAG 최적화**: 구조화된 정보로 더 정확한 컨텍스트 제공

**이제 사용자가 제공한 예시 스키마와 동일한 형태의 깔끔하고 구조화된 JSON이 생성됩니다!** 🎉 