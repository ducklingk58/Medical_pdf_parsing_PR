import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging
from config.settings import Settings

def validate_processing_results(output_dir: str) -> Dict[str, Any]:
    """처리 결과 검증"""
    output_path = Path(output_dir)
    validation_results = {
        "total_files": 0,
        "valid_files": 0,
        "invalid_files": 0,
        "issues": [],
        "quality_score": 0.0
    }
    
    try:
        for summary_file in output_path.rglob("summary.json"):
            validation_results["total_files"] += 1
            
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                
                # 기본 검증
                issues = []
                
                # 텍스트 블록 검증
                if summary.get("text_blocks_count", 0) == 0:
                    issues.append("텍스트 블록이 없음")
                
                # 표 데이터 검증
                if summary.get("tables_count", 0) > 0:
                    # 표가 있는데 구조화된 데이터가 없는 경우
                    pass  # 추가 검증 로직
                
                # 이미지 검증
                if summary.get("images_count", 0) > 0:
                    # 이미지가 있는데 메타데이터가 없는 경우
                    pass  # 추가 검증 로직
                
                # RAG 청크 검증
                if summary.get("rag_chunks_count", 0) == 0 and summary.get("text_blocks_count", 0) > 0:
                    issues.append("RAG 청크가 생성되지 않음")
                
                if issues:
                    validation_results["invalid_files"] += 1
                    validation_results["issues"].append({
                        "file": summary_file.parent.name,
                        "issues": issues,
                        "summary": summary
                    })
                else:
                    validation_results["valid_files"] += 1
                    
            except Exception as e:
                validation_results["invalid_files"] += 1
                validation_results["issues"].append({
                    "file": summary_file.parent.name,
                    "issues": [f"파일 로드 오류: {str(e)}"],
                    "summary": {}
                })
        
        # 품질 점수 계산
        if validation_results["total_files"] > 0:
            validation_results["quality_score"] = validation_results["valid_files"] / validation_results["total_files"]
        
    except Exception as e:
        logging.error(f"검증 중 오류 발생: {str(e)}")
    
    return validation_results

def generate_quality_report(output_dir: str) -> pd.DataFrame:
    """품질 보고서 생성"""
    summaries = []
    output_path = Path(output_dir)
    
    try:
        for summary_file in output_path.rglob("summary.json"):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    summary['filename'] = summary_file.parent.name
                    summary['file_path'] = str(summary_file.parent)
                    summaries.append(summary)
            except Exception as e:
                logging.warning(f"요약 파일 로드 오류: {summary_file} - {str(e)}")
                continue
        
        if not summaries:
            return pd.DataFrame()
        
        df = pd.DataFrame(summaries)
        
        # 품질 지표 계산
        df['avg_words_per_block'] = df['total_words'] / (df['text_blocks_count'] + 1)
        df['blocks_per_table'] = df['text_blocks_count'] / (df['tables_count'] + 1)
        df['chunks_per_block'] = df['rag_chunks_count'] / (df['text_blocks_count'] + 1)
        df['tokens_per_word'] = df['total_tokens_estimate'] / (df['total_words'] + 1)
        
        # 품질 점수 계산
        df['quality_score'] = 0.0
        
        # 텍스트 블록 점수
        df.loc[df['text_blocks_count'] > 0, 'quality_score'] += 0.3
        
        # 표 데이터 점수
        df.loc[df['tables_count'] > 0, 'quality_score'] += 0.2
        
        # RAG 청크 점수
        df.loc[df['rag_chunks_count'] > 0, 'quality_score'] += 0.3
        
        # 단어 수 점수 (적절한 크기)
        word_score = df['total_words'].apply(lambda x: min(1.0, x / 1000) * 0.2)
        df['quality_score'] += word_score
        
        return df
        
    except Exception as e:
        logging.error(f"품질 보고서 생성 오류: {str(e)}")
        return pd.DataFrame()

def analyze_processing_patterns(output_dir: str) -> Dict[str, Any]:
    """처리 패턴 분석"""
    df = generate_quality_report(output_dir)
    
    if df.empty:
        return {}
    
    analysis = {
        "file_count": len(df),
        "avg_text_blocks": df['text_blocks_count'].mean(),
        "avg_tables": df['tables_count'].mean(),
        "avg_images": df['images_count'].mean(),
        "avg_chunks": df['rag_chunks_count'].mean(),
        "avg_words": df['total_words'].mean(),
        "avg_quality_score": df['quality_score'].mean(),
        
        # 분포 정보
        "text_blocks_distribution": {
            "min": df['text_blocks_count'].min(),
            "max": df['text_blocks_count'].max(),
            "median": df['text_blocks_count'].median(),
            "std": df['text_blocks_count'].std()
        },
        
        "tables_distribution": {
            "min": df['tables_count'].min(),
            "max": df['tables_count'].max(),
            "median": df['tables_count'].median(),
            "std": df['tables_count'].std()
        },
        
        # 이상치 탐지
        "outliers": {
            "no_text_files": len(df[df['text_blocks_count'] == 0]),
            "high_table_files": len(df[df['tables_count'] > df['tables_count'].quantile(0.9)]),
            "low_quality_files": len(df[df['quality_score'] < 0.5])
        }
    }
    
    return analysis

def export_validation_report(output_dir: str, report_path: str = None):
    """검증 보고서 내보내기"""
    if report_path is None:
        report_path = Path(output_dir) / "validation_report.json"
    
    # 검증 수행
    validation_results = validate_processing_results(output_dir)
    
    # 품질 분석
    quality_analysis = analyze_processing_patterns(output_dir)
    
    # 품질 보고서 데이터프레임
    quality_df = generate_quality_report(output_dir)
    
    # 종합 보고서 생성
    report = {
        "validation_results": validation_results,
        "quality_analysis": quality_analysis,
        "timestamp": pd.Timestamp.now().isoformat(),
        "output_directory": output_dir
    }
    
    # JSON 보고서 저장
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Excel 보고서 저장 (품질 데이터프레임)
    if not quality_df.empty:
        excel_path = Path(report_path).with_suffix('.xlsx')
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            quality_df.to_excel(writer, sheet_name='Quality_Report', index=False)
            
            # 요약 시트 추가
            summary_data = {
                'Metric': ['Total Files', 'Valid Files', 'Invalid Files', 'Quality Score'],
                'Value': [
                    validation_results['total_files'],
                    validation_results['valid_files'],
                    validation_results['invalid_files'],
                    f"{validation_results['quality_score']:.2%}"
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    return report

def check_file_integrity(output_dir: str) -> Dict[str, Any]:
    """파일 무결성 검사"""
    output_path = Path(output_dir)
    integrity_results = {
        "total_directories": 0,
        "complete_directories": 0,
        "incomplete_directories": 0,
        "missing_files": [],
        "corrupted_files": []
    }
    
    try:
        # 각 PDF별 출력 디렉토리 검사
        for pdf_dir in output_path.iterdir():
            if pdf_dir.is_dir() and pdf_dir.name != "logs":
                integrity_results["total_directories"] += 1
                
                required_files = [
                    "summary.json",
                    "metadata.json",
                    "final_markdown.md"
                ]
                
                missing_files = []
                corrupted_files = []
                
                for required_file in required_files:
                    file_path = pdf_dir / required_file
                    if not file_path.exists():
                        missing_files.append(required_file)
                    else:
                        # 파일 무결성 검사
                        try:
                            if required_file.endswith('.json'):
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    json.load(f)
                        except Exception as e:
                            corrupted_files.append(f"{required_file}: {str(e)}")
                
                if missing_files or corrupted_files:
                    integrity_results["incomplete_directories"] += 1
                    integrity_results["missing_files"].append({
                        "directory": pdf_dir.name,
                        "missing": missing_files,
                        "corrupted": corrupted_files
                    })
                else:
                    integrity_results["complete_directories"] += 1
                    
    except Exception as e:
        logging.error(f"무결성 검사 중 오류: {str(e)}")
    
    return integrity_results

def generate_processing_statistics(output_dir: str) -> Dict[str, Any]:
    """처리 통계 생성"""
    df = generate_quality_report(output_dir)
    
    if df.empty:
        return {}
    
    stats = {
        "total_files_processed": len(df),
        "total_text_blocks": df['text_blocks_count'].sum(),
        "total_tables": df['tables_count'].sum(),
        "total_images": df['images_count'].sum(),
        "total_rag_chunks": df['rag_chunks_count'].sum(),
        "total_words": df['total_words'].sum(),
        "total_tokens": df['total_tokens_estimate'].sum(),
        
        "averages": {
            "text_blocks_per_file": df['text_blocks_count'].mean(),
            "tables_per_file": df['tables_count'].mean(),
            "images_per_file": df['images_count'].mean(),
            "chunks_per_file": df['rag_chunks_count'].mean(),
            "words_per_file": df['total_words'].mean(),
            "tokens_per_file": df['total_tokens_estimate'].mean()
        },
        
        "percentiles": {
            "text_blocks": {
                "25%": df['text_blocks_count'].quantile(0.25),
                "50%": df['text_blocks_count'].quantile(0.50),
                "75%": df['text_blocks_count'].quantile(0.75),
                "90%": df['text_blocks_count'].quantile(0.90)
            },
            "tables": {
                "25%": df['tables_count'].quantile(0.25),
                "50%": df['tables_count'].quantile(0.50),
                "75%": df['tables_count'].quantile(0.75),
                "90%": df['tables_count'].quantile(0.90)
            }
        }
    }
    
    return stats 