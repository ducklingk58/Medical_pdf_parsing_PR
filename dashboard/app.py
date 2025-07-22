import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os
import tempfile
import shutil

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import Settings
from utils.pdf_processor import PDFProcessor
from Medical_pdf_processor_enhanced import EnhancedPDFProcessor
from utils.logger import setup_logger

def load_summary_data(output_dir: str):
    """배치 처리 요약 데이터 로드"""
    summary_path = Path(output_dir) / "batch_summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"요약 파일 로드 오류: {str(e)}")
    return None

def load_individual_summaries(output_dir: str):
    """개별 파일 요약 데이터 로드"""
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
                st.error(f"개별 요약 파일 로드 오류: {summary_file} - {str(e)}")
    except Exception as e:
        st.error(f"요약 파일 검색 오류: {str(e)}")
    
    return summaries

def format_time(seconds):
    """초를 읽기 쉬운 시간 형식으로 변환"""
    if seconds < 60:
        return f"{seconds:.1f}초"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}분"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}시간"

def process_uploaded_pdf(uploaded_file, output_dir: str, use_enhanced: bool = True):
    """업로드된 PDF 파일 처리"""
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        # 출력 디렉토리 생성
        output_path = Path(output_dir) / "uploaded_files" / uploaded_file.name.replace('.pdf', '')
        output_path.mkdir(parents=True, exist_ok=True)
        
        # PDF 처리기 초기화 (향상된 처리기 사용)
        if use_enhanced:
            processor = EnhancedPDFProcessor(use_gpu=False)
            # PDF 처리
            with st.spinner(f"향상된 PDF 처리 중: {uploaded_file.name}..."):
                summary = processor.process_pdf_enhanced(str(tmp_path), str(output_path))
        else:
            processor = PDFProcessor()
            # PDF 처리
            with st.spinner(f"기본 PDF 처리 중: {uploaded_file.name}..."):
                summary = processor.process_pdf(str(tmp_path), str(output_path))
        
        # 임시 파일 삭제
        os.unlink(tmp_path)
        
        return summary, str(output_path)
        
    except Exception as e:
        st.error(f"PDF 처리 중 오류 발생: {str(e)}")
        return None, None

def find_json_files(output_dir: str):
    """출력 디렉토리에서 모든 JSON 파일 찾기"""
    json_files = []
    output_path = Path(output_dir)
    
    try:
        for json_file in output_path.rglob("*.json"):
            try:
                # 파일 크기 확인
                file_size = json_file.stat().st_size
                
                # 파일 정보 수집
                file_info = {
                    'name': json_file.name,
                    'path': str(json_file),
                    'relative_path': str(json_file.relative_to(output_path)),
                    'size': file_size,
                    'size_mb': file_size / (1024 * 1024),
                    'parent_dir': json_file.parent.name,
                    'modified_time': datetime.fromtimestamp(json_file.stat().st_mtime)
                }
                json_files.append(file_info)
            except Exception as e:
                st.error(f"JSON 파일 정보 수집 오류: {json_file} - {str(e)}")
    except Exception as e:
        st.error(f"JSON 파일 검색 오류: {str(e)}")
    
    return json_files

def load_json_content(file_path: str):
    """JSON 파일 내용 로드"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"JSON 파일 로드 오류: {str(e)}")
        return None

def format_json_for_display(data, max_depth=3, current_depth=0):
    """JSON 데이터를 표시용으로 포맷팅"""
    if current_depth >= max_depth:
        if isinstance(data, dict):
            return f"{{...}} ({len(data)} items)"
        elif isinstance(data, list):
            return f"[...] ({len(data)} items)"
        else:
            return str(data)
    
    if isinstance(data, dict):
        formatted = {}
        for key, value in data.items():
            formatted[key] = format_json_for_display(value, max_depth, current_depth + 1)
        return formatted
    elif isinstance(data, list):
        if len(data) > 10:  # 리스트가 너무 길면 처음 5개만 표시
            return [format_json_for_display(item, max_depth, current_depth + 1) for item in data[:5]] + [f"... ({len(data) - 5} more items)"]
        else:
            return [format_json_for_display(item, max_depth, current_depth + 1) for item in data]
    else:
        return data

def main():
    st.set_page_config(
        page_title="Medical PDF 파싱 결과 대시보드",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏥 Medical PDF 파싱 결과 대시보드")
    st.markdown("---")
    
    # 사이드바 설정
    st.sidebar.header("⚙️ 설정")
    output_dir = st.sidebar.text_input(
        "출력 디렉토리 경로", 
        value=str(Settings.OUTPUT_DIR)
    )
    
    if st.sidebar.button("🔄 데이터 새로고침"):
        st.rerun()
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 배치 처리 결과", "📁 PDF 업로드 & 파싱", "🔍 개별 파일 분석", "📄 JSON 미리보기"])
    
    with tab1:
        # 배치 요약 표시
        st.header("📈 배치 처리 요약")
        batch_summary = load_summary_data(output_dir)
        
        if batch_summary:
            # 메트릭 카드
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "총 파일 수", 
                    batch_summary['total_files'],
                    help="처리 대상이었던 총 PDF 파일 수"
                )
            
            with col2:
                st.metric(
                    "성공한 파일 수", 
                    batch_summary['successful_files'],
                    delta=batch_summary['successful_files'] - batch_summary['failed_files'],
                    help="성공적으로 처리된 파일 수"
                )
            
            with col3:
                st.metric(
                    "실패한 파일 수", 
                    batch_summary['failed_files'],
                    delta=batch_summary['failed_files'] - batch_summary['successful_files'],
                    delta_color="inverse",
                    help="처리 중 오류가 발생한 파일 수"
                )
            
            with col4:
                success_rate = batch_summary['success_rate'] * 100
                st.metric(
                    "성공률", 
                    f"{success_rate:.1f}%",
                    help="성공한 파일의 비율"
                )
            
            # 처리 시간 정보
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "총 처리 시간",
                    format_time(batch_summary['total_processing_time']),
                    help="전체 배치 처리에 소요된 시간"
                )
            
            with col2:
                st.metric(
                    "평균 처리 시간",
                    format_time(batch_summary['average_processing_time']),
                    help="파일당 평균 처리 시간"
                )
            
            # 성공률 파이 차트
            fig = go.Figure(data=[
                go.Pie(
                    labels=['성공', '실패'],
                    values=[batch_summary['successful_files'], batch_summary['failed_files']],
                    hole=0.3,
                    marker_colors=['#00FF00', '#FF0000'],
                    textinfo='label+percent',
                    textfont_size=14
                )
            ])
            fig.update_layout(
                title="처리 결과 분포",
                showlegend=True,
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("⚠️ 배치 요약 데이터를 찾을 수 없습니다. 출력 디렉토리를 확인해주세요.")
    
    with tab2:
        st.header("📁 PDF 파일 업로드 & 파싱")
        st.markdown("""
        ### 🚀 대량 PDF 파싱 기능
        
        이 시스템은 **대량의 PDF 파일을 효율적으로 처리**할 수 있도록 설계되었습니다:
        
        - ✅ **병렬 처리**: 여러 PDF 파일을 동시에 처리
        - ✅ **메모리 최적화**: 대용량 파일도 안정적으로 처리
        - ✅ **진행률 모니터링**: 실시간 처리 상황 확인
        - ✅ **오류 복구**: 개별 파일 실패가 전체를 중단하지 않음
        - ✅ **자동 검증**: 처리 결과 품질 자동 검사
        
        **500개 이상의 PDF 파일도 안정적으로 처리 가능합니다!**
        """)
        
        # 파일 업로드 섹션
        st.subheader("📤 PDF 파일 업로드")
        
        # 단일 파일 업로드
        uploaded_file = st.file_uploader(
            "PDF 파일을 선택하세요",
            type=['pdf'],
            help="처리할 PDF 파일을 업로드하세요"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ 파일 업로드 완료: {uploaded_file.name}")
            
            # 파일 정보 표시
            col1, col2 = st.columns(2)
            with col1:
                st.metric("파일명", uploaded_file.name)
            with col2:
                st.metric("파일 크기", f"{uploaded_file.size / 1024:.1f} KB")
            
            # 처리 옵션 설정
            st.subheader("⚙️ 처리 옵션")
            col1, col2 = st.columns(2)
            with col1:
                use_enhanced = st.checkbox(
                    "🚀 향상된 처리 사용", 
                    value=True,
                    help="LayoutParser + PaddleOCR 기반 고급 테이블/이미지 파싱"
                )
            with col2:
                use_gpu = st.checkbox(
                    "🎮 GPU 가속 사용", 
                    value=False,
                    help="GPU 가속으로 처리 속도 향상 (GPU 필요)"
                )
            
            # 처리 버튼
            if st.button("🚀 PDF 파싱 시작", type="primary"):
                # 처리 실행
                summary, output_path = process_uploaded_pdf(uploaded_file, output_dir, use_enhanced)
                
                if summary:
                    st.success("✅ PDF 파싱 완료!")
                    
                    # 결과 표시
                    st.subheader("📊 파싱 결과")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("텍스트 블록", summary['text_blocks_count'])
                    with col2:
                        st.metric("표", summary['tables_count'])
                    with col3:
                        st.metric("이미지", summary['images_count'])
                    with col4:
                        st.metric("RAG 청크", summary['rag_chunks_count'])
                    
                    # 추가 정보
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("총 단어 수", f"{summary['total_words']:,}")
                    with col2:
                        st.metric("추정 토큰 수", f"{summary['total_tokens_estimate']:,.0f}")
                    
                    # 결과 파일 다운로드
                    st.subheader("📥 결과 파일 다운로드")
                    
                    # 마크다운 파일
                    md_path = Path(output_path) / "final_markdown.md"
                    if md_path.exists():
                        with open(md_path, 'r', encoding='utf-8') as f:
                            md_content = f.read()
                        st.download_button(
                            label="📄 마크다운 파일 다운로드",
                            data=md_content,
                            file_name=f"{uploaded_file.name.replace('.pdf', '')}_parsed.md",
                            mime="text/markdown"
                        )
                    
                    # JSON 메타데이터
                    metadata_path = Path(output_path) / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata_content = f.read()
                        st.download_button(
                            label="📋 메타데이터 JSON 다운로드",
                            data=metadata_content,
                            file_name=f"{uploaded_file.name.replace('.pdf', '')}_metadata.json",
                            mime="application/json"
                        )
                    
                    # 요약 정보
                    summary_path = Path(output_path) / "summary.json"
                    if summary_path.exists():
                        with open(summary_path, 'r', encoding='utf-8') as f:
                            summary_content = f.read()
                        st.download_button(
                            label="📊 요약 정보 JSON 다운로드",
                            data=summary_content,
                            file_name=f"{uploaded_file.name.replace('.pdf', '')}_summary.json",
                            mime="application/json"
                        )
        
        # 대량 처리 안내
        st.markdown("---")
        st.subheader("📚 대량 처리 방법")
        st.markdown("""
        ### 배치 처리로 대량 PDF 파싱하기
        
        터미널에서 다음 명령어를 실행하세요:
        
        ```bash
        # 기본 실행 (input_pdfs 폴더의 모든 PDF 처리)
        python run_processing.py
        
        # 워커 수 지정 (더 빠른 처리)
        python run_processing.py --workers 8
        
        # 커스텀 입력/출력 디렉토리
        python run_processing.py --input ./my_pdfs --output ./my_results
        
        # 검증 보고서 생성
        python run_processing.py --create-report
        ```
        
        ### 처리 성능
        - **4코어 CPU**: 약 2-3초/파일
        - **8코어 CPU**: 약 1-2초/파일  
        - **500개 파일**: 약 10-15분 (8코어 기준)
        """)
    
    with tab3:
        # 개별 파일 상세 정보
        st.header("📋 개별 파일 상세 정보")
        individual_summaries = load_individual_summaries(output_dir)
        
        if individual_summaries:
            # 데이터프레임으로 변환
            df = pd.DataFrame(individual_summaries)
            
            # 기본 통계 정보
            st.subheader("📊 기본 통계")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("평균 텍스트 블록", f"{df['text_blocks_count'].mean():.1f}")
            with col2:
                st.metric("평균 표 수", f"{df['tables_count'].mean():.1f}")
            with col3:
                st.metric("평균 이미지 수", f"{df['images_count'].mean():.1f}")
            with col4:
                st.metric("평균 RAG 청크", f"{df['rag_chunks_count'].mean():.1f}")
            
            # 통계 차트
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.histogram(
                    df, 
                    x='text_blocks_count', 
                    title="텍스트 블록 수 분포",
                    nbins=20,
                    color_discrete_sequence=['#1f77b4']
                )
                fig1.update_layout(xaxis_title="텍스트 블록 수", yaxis_title="파일 수")
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.histogram(
                    df, 
                    x='tables_count', 
                    title="표 수 분포",
                    nbins=20,
                    color_discrete_sequence=['#ff7f0e']
                )
                fig2.update_layout(xaxis_title="표 수", yaxis_title="파일 수")
                st.plotly_chart(fig2, use_container_width=True)
            
            # 추가 통계 차트
            col1, col2 = st.columns(2)
            
            with col1:
                fig3 = px.histogram(
                    df, 
                    x='images_count', 
                    title="이미지 수 분포",
                    nbins=20,
                    color_discrete_sequence=['#2ca02c']
                )
                fig3.update_layout(xaxis_title="이미지 수", yaxis_title="파일 수")
                st.plotly_chart(fig3, use_container_width=True)
            
            with col2:
                fig4 = px.histogram(
                    df, 
                    x='rag_chunks_count', 
                    title="RAG 청크 수 분포",
                    nbins=20,
                    color_discrete_sequence=['#d62728']
                )
                fig4.update_layout(xaxis_title="RAG 청크 수", yaxis_title="파일 수")
                st.plotly_chart(fig4, use_container_width=True)
            
            # 상세 테이블
            st.subheader("📄 파일별 상세 정보")
            
            # 컬럼 선택
            columns_to_show = st.multiselect(
                "표시할 컬럼 선택",
                options=['filename', 'text_blocks_count', 'tables_count', 'images_count', 
                        'rag_chunks_count', 'total_words', 'total_tokens_estimate'],
                default=['filename', 'text_blocks_count', 'tables_count', 'images_count', 'rag_chunks_count']
            )
            
            if columns_to_show:
                display_df = df[columns_to_show].copy()
                st.dataframe(display_df, use_container_width=True)
            
            # 파일 선택하여 상세 보기
            st.subheader("🔍 개별 파일 상세 보기")
            selected_file = st.selectbox(
                "파일 선택",
                options=df['filename'].tolist(),
                help="상세 정보를 확인할 파일을 선택하세요"
            )
            
            if selected_file:
                file_summary = df[df['filename'] == selected_file].iloc[0]
                
                # 파일 정보 카드
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("텍스트 블록", file_summary['text_blocks_count'])
                with col2:
                    st.metric("표", file_summary['tables_count'])
                with col3:
                    st.metric("이미지", file_summary['images_count'])
                with col4:
                    st.metric("RAG 청크", file_summary['rag_chunks_count'])
                
                # 추가 정보
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("총 단어 수", f"{file_summary['total_words']:,}")
                with col2:
                    st.metric("추정 토큰 수", f"{file_summary['total_tokens_estimate']:,.0f}")
                
                # 파일 경로 정보
                st.info(f"📁 파일 경로: {file_summary['file_path']}")
                
                # 처리 설정 정보
                if 'settings' in file_summary:
                    st.subheader("⚙️ 처리 설정")
                    settings_df = pd.DataFrame([file_summary['settings']])
                    st.dataframe(settings_df, use_container_width=True)
        
        else:
            st.warning("⚠️ 개별 파일 요약 데이터를 찾을 수 없습니다.")
    
    with tab4:
        # JSON 파일 미리보기
        st.header("📄 JSON 파일 미리보기")
        st.markdown("파싱된 JSON 파일들을 탐색하고 미리보기할 수 있습니다.")
        
        # JSON 파일 목록 로드
        json_files = find_json_files(output_dir)
        
        if json_files:
            st.subheader("📁 JSON 파일 목록")
            
            # 파일 정보를 데이터프레임으로 변환
            df_files = pd.DataFrame(json_files)
            df_files['modified_time'] = pd.to_datetime(df_files['modified_time'])
            
            # 파일 크기별 색상 구분
            def get_size_color(size_mb):
                if size_mb < 1:
                    return "🟢"
                elif size_mb < 5:
                    return "🟡"
                else:
                    return "🔴"
            
            df_files['size_icon'] = df_files['size_mb'].apply(get_size_color)
            df_files['display_name'] = df_files['size_icon'] + " " + df_files['name']
            
            # 파일 선택
            selected_file_display = st.selectbox(
                "JSON 파일 선택",
                options=df_files['display_name'].tolist(),
                help="미리보기할 JSON 파일을 선택하세요"
            )
            
            if selected_file_display:
                # 선택된 파일 정보 가져오기
                selected_file_info = df_files[df_files['display_name'] == selected_file_display].iloc[0]
                
                # 파일 정보 표시
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("파일명", selected_file_info['name'])
                with col2:
                    st.metric("파일 크기", f"{selected_file_info['size_mb']:.2f} MB")
                with col3:
                    st.metric("수정 시간", selected_file_info['modified_time'].strftime("%Y-%m-%d %H:%M"))
                with col4:
                    st.metric("상위 디렉토리", selected_file_info['parent_dir'])
                
                # 파일 경로 표시
                st.info(f"📁 파일 경로: {selected_file_info['relative_path']}")
                
                # JSON 내용 로드 및 표시
                st.subheader("📋 JSON 내용 미리보기")
                
                # 표시 옵션
                col1, col2 = st.columns(2)
                with col1:
                    max_depth = st.slider("최대 깊이", 1, 5, 3, help="JSON 구조의 최대 표시 깊이")
                with col2:
                    show_raw = st.checkbox("원본 JSON 표시", help="원본 JSON 형식으로 표시")
                
                # JSON 내용 로드
                json_content = load_json_content(selected_file_info['path'])
                
                if json_content is not None:
                    if show_raw:
                        # 원본 JSON 표시
                        st.json(json_content)
                    else:
                        # 포맷팅된 JSON 표시
                        formatted_content = format_json_for_display(json_content, max_depth)
                        st.json(formatted_content)
                    
                    # JSON 구조 분석
                    st.subheader("🔍 JSON 구조 분석")
                    
                    def analyze_json_structure(data, path=""):
                        """JSON 구조 분석"""
                        structure = {}
                        if isinstance(data, dict):
                            for key, value in data.items():
                                current_path = f"{path}.{key}" if path else key
                                if isinstance(value, (dict, list)):
                                    structure[current_path] = {
                                        'type': type(value).__name__,
                                        'size': len(value) if hasattr(value, '__len__') else 'N/A'
                                    }
                                    # 재귀적으로 분석 (깊이 제한)
                                    if len(current_path.split('.')) < 3:
                                        sub_structure = analyze_json_structure(value, current_path)
                                        structure.update(sub_structure)
                                else:
                                    structure[current_path] = {
                                        'type': type(value).__name__,
                                        'value': str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                                    }
                        elif isinstance(data, list):
                            if data:
                                # 첫 번째 요소로 타입 추정
                                sample = data[0]
                                structure[f"{path}[0]" if path else "[0]"] = {
                                    'type': f"list of {type(sample).__name__}",
                                    'size': len(data)
                                }
                        return structure
                    
                    structure_analysis = analyze_json_structure(json_content)
                    
                    if structure_analysis:
                        # 구조를 데이터프레임으로 변환
                        structure_df = pd.DataFrame([
                            {
                                '경로': path,
                                '타입': info['type'],
                                '크기': info.get('size', 'N/A'),
                                '값': info.get('value', 'N/A')
                            }
                            for path, info in structure_analysis.items()
                        ])
                        
                        st.dataframe(structure_df, use_container_width=True)
                    
                    # 다운로드 버튼
                    st.subheader("📥 파일 다운로드")
                    with open(selected_file_info['path'], 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    st.download_button(
                        label="📄 JSON 파일 다운로드",
                        data=file_content,
                        file_name=selected_file_info['name'],
                        mime="application/json"
                    )
                else:
                    st.error("JSON 파일을 로드할 수 없습니다.")
            
            # 파일 목록 테이블
            st.subheader("📊 전체 JSON 파일 목록")
            
            # 필터링 옵션
            col1, col2 = st.columns(2)
            with col1:
                min_size = st.number_input("최소 파일 크기 (MB)", 0.0, 100.0, 0.0, 0.1)
            with col2:
                file_type_filter = st.selectbox(
                    "파일 타입 필터",
                    ["전체", "summary.json", "metadata.json", "기타"],
                    help="특정 타입의 JSON 파일만 표시"
                )
            
            # 필터링 적용
            filtered_df = df_files.copy()
            if min_size > 0:
                filtered_df = filtered_df[filtered_df['size_mb'] >= min_size]
            
            if file_type_filter != "전체":
                if file_type_filter == "summary.json":
                    filtered_df = filtered_df[filtered_df['name'] == 'summary.json']
                elif file_type_filter == "metadata.json":
                    filtered_df = filtered_df[filtered_df['name'] == 'metadata.json']
                else:
                    filtered_df = filtered_df[~filtered_df['name'].isin(['summary.json', 'metadata.json'])]
            
            # 표시할 컬럼 선택
            display_columns = ['name', 'size_mb', 'parent_dir', 'modified_time']
            display_df = filtered_df[display_columns].copy()
            display_df.columns = ['파일명', '크기 (MB)', '상위 디렉토리', '수정 시간']
            display_df['수정 시간'] = display_df['수정 시간'].dt.strftime("%Y-%m-%d %H:%M")
            
            st.dataframe(display_df, use_container_width=True)
            
            # 통계 정보
            st.subheader("📈 JSON 파일 통계")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 JSON 파일 수", len(df_files))
            with col2:
                st.metric("총 크기", f"{df_files['size_mb'].sum():.2f} MB")
            with col3:
                st.metric("평균 파일 크기", f"{df_files['size_mb'].mean():.2f} MB")
            with col4:
                st.metric("최대 파일 크기", f"{df_files['size_mb'].max():.2f} MB")
        
        else:
            st.warning("⚠️ JSON 파일을 찾을 수 없습니다. 출력 디렉토리를 확인해주세요.")
    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        <p>Medical PDF 파싱 프로젝트 - Unstructured 기반 고급 파싱 시스템</p>
        <p>개발: Medical_pdf_parsing_PR | 대량 PDF 처리 지원</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 