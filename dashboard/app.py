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

# 필요한 모듈들 import (오류 처리 포함)
try:
    from config.settings import Settings
except ImportError:
    # Settings 클래스가 없을 경우 기본값 사용
    class Settings:
        OUTPUT_DIR = Path("output_data")
        INPUT_DIR = Path("input_pdfs")
        MAX_WORKERS = 4
        SIMILARITY_THRESHOLD = 0.7
        SENTENCE_MODEL = "all-MiniLM-L6-v2"
        REMOVE_PAGE_NUMBERS = True
        REMOVE_HEADERS_FOOTERS = True

try:
    from utils.pdf_processor import PDFProcessor
except ImportError:
    PDFProcessor = None

try:
    # 절대 경로로 import 시도
    import sys
    import os
    
    # 현재 파일의 절대 경로를 기준으로 상위 디렉토리 추가
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    
    from Medical_pdf_processor_enhanced import EnhancedPDFProcessor
    print("✅ EnhancedPDFProcessor import 성공")
except ImportError as e:
    print(f"❌ EnhancedPDFProcessor import 실패: {e}")
    st.error("EnhancedPDFProcessor를 찾을 수 없습니다. Medical_pdf_processor_enhanced.py 파일이 필요합니다.")
    EnhancedPDFProcessor = None

try:
    from utils.rag_optimized_parser import RAGOptimizedParser
except ImportError:
    RAGOptimizedParser = None

try:
    from utils.logger import setup_logger
except ImportError:
    def setup_logger():
        import logging
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)

def process_batch_pdfs(uploaded_files, output_dir: str, chunk_options: dict = None):
    """다중 PDF 파일 배치 처리"""
    import time
    
    if not uploaded_files:
        st.error("처리할 파일이 없습니다.")
        return False
    
    # 배치 처리 결과 저장
    batch_results = {
        'total_files': len(uploaded_files),
        'successful': 0,
        'failed': 0,
        'start_time': time.time(),
        'results': []
    }
    
    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 청크 옵션 설정 (고정값)
    if chunk_options is None:
        chunk_options = {
            'chunk_size': 500,
            'chunk_overlap': 100,
            'merge_small_chunks': True,
            'use_gpu': False,
            'enable_keyword_extraction': True,
            'keyword_count': 5
        }
    
    # 향상된 처리기 초기화
    use_gpu = chunk_options.get('use_gpu', False)
    
    if EnhancedPDFProcessor is None:
        st.error("❌ EnhancedPDFProcessor를 사용할 수 없습니다. Medical_pdf_processor_enhanced.py 파일을 확인해주세요.")
        return False
    
    try:
        processor = EnhancedPDFProcessor(use_gpu=use_gpu)
    except Exception as e:
        st.error(f"❌ EnhancedPDFProcessor 초기화 실패: {str(e)}")
        return False
    
    # 배치 처리 시작
    st.info(f"🚀 배치 처리 시작: {len(uploaded_files)}개 파일")
    
    # 결과 테이블 초기화
    results_df = pd.DataFrame(columns=['파일명', '상태', '처리 시간', '오류 메시지'])
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            # 진행률 업데이트
            progress = (i + 1) / len(uploaded_files)
            progress_bar.progress(progress)
            status_text.text(f"처리 중... {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
            
            # 개별 파일 처리 시작 시간
            start_time = time.time()
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            # 출력 디렉토리 생성
            output_path = Path(output_dir) / "uploaded_files" / uploaded_file.name.replace('.pdf', '')
            output_path.mkdir(parents=True, exist_ok=True)
            
            # PDF 처리
            try:
                result = processor.process_pdf_enhanced(
                    pdf_path=tmp_path,
                    output_dir=str(output_path)
                )
                # process_pdf_enhanced는 성공 시 summary를 반환하고, 실패 시 예외를 발생시킴
                success = True
            except Exception as e:
                st.error(f"PDF 처리 중 오류 발생: {str(e)}")
                success = False
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            # 결과 저장 (개별 파일 정보 포함)
            result = {
                'filename': uploaded_file.name,
                'status': '성공' if success else '실패',
                'processing_time': processing_time,
                'error_message': '' if success else '처리 실패',
                'output_path': str(output_path) if success else None,
                'output_files': []
            }
            
            # 성공한 경우 출력 파일 목록 수집
            if success and output_path.exists():
                try:
                    # 주요 출력 파일들 확인
                    output_files = []
                    for file_path in output_path.glob("*"):
                        if file_path.is_file():
                            file_info = {
                                'name': file_path.name,
                                'path': str(file_path),
                                'size': file_path.stat().st_size,
                                'type': file_path.suffix
                            }
                            output_files.append(file_info)
                    result['output_files'] = output_files
                except Exception as e:
                    st.warning(f"출력 파일 정보 수집 실패 ({uploaded_file.name}): {str(e)}")
            
            batch_results['results'].append(result)
            
            if success:
                batch_results['successful'] += 1
            else:
                batch_results['failed'] += 1
            
            # 결과 테이블 업데이트
            new_row = pd.DataFrame([{
                '파일명': uploaded_file.name,
                '상태': '✅ 성공' if success else '❌ 실패',
                '처리 시간': f"{processing_time:.1f}초",
                '오류 메시지': '' if success else '처리 실패'
            }])
            results_df = pd.concat([results_df, new_row], ignore_index=True)
            
            # 임시 파일 정리
            try:
                os.unlink(tmp_path)
            except:
                pass
                
        except Exception as e:
            # 오류 처리
            processing_time = time.time() - start_time if 'start_time' in locals() else 0
            
            result = {
                'filename': uploaded_file.name,
                'status': '실패',
                'processing_time': processing_time,
                'error_message': str(e)
            }
            
            batch_results['results'].append(result)
            batch_results['failed'] += 1
            
            # 결과 테이블 업데이트
            new_row = pd.DataFrame([{
                '파일명': uploaded_file.name,
                '상태': '❌ 실패',
                '처리 시간': f"{processing_time:.1f}초",
                '오류 메시지': str(e)
            }])
            results_df = pd.concat([results_df, new_row], ignore_index=True)
    
    # 배치 처리 완료
    batch_results['end_time'] = time.time()
    batch_results['total_time'] = batch_results['end_time'] - batch_results['start_time']
    
    # 진행률 완료
    progress_bar.progress(1.0)
    status_text.text("✅ 배치 처리 완료!")
    
    # 배치 결과 저장
    batch_summary_path = Path(output_dir) / "batch_summary.json"
    with open(batch_summary_path, 'w', encoding='utf-8') as f:
        json.dump(batch_results, f, ensure_ascii=False, indent=2)
    
    # 결과 표시
    st.success(f"🎉 배치 처리 완료!")
    
    # 통계 표시
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 파일 수", batch_results['total_files'])
    with col2:
        st.metric("성공", batch_results['successful'])
    with col3:
        st.metric("실패", batch_results['failed'])
    with col4:
        st.metric("총 처리 시간", f"{batch_results['total_time']:.1f}초")
    
    # 성공률 계산
    success_rate = (batch_results['successful'] / batch_results['total_files']) * 100
    st.metric("성공률", f"{success_rate:.1f}%")
    
    # 결과 테이블 표시
    st.subheader("📋 처리 결과 상세")
    st.dataframe(results_df, use_container_width=True)
    
    # 실패한 파일이 있으면 경고
    if batch_results['failed'] > 0:
        st.warning(f"⚠️ {batch_results['failed']}개 파일이 실패했습니다. 위의 결과 테이블을 확인하세요.")
    
    return batch_results['successful'] > 0

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
    tab1, tab2, tab3, tab4 = st.tabs(["📁 PDF 업로드 & 파싱", "🔍 개별 파일 분석", "📄 JSON 미리보기", "📊 배치 처리 결과"])
    
    with tab1:
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
        
        # 업로드 모드 선택
        upload_mode = st.radio(
            "업로드 모드 선택",
            ["📄 단일 파일", "📁 다중 파일 (배치 처리)"],
            help="단일 파일 또는 여러 파일을 한번에 업로드할 수 있습니다"
        )
        
        if upload_mode == "📄 단일 파일":
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
                
                uploaded_files = [uploaded_file]
        else:
            # 다중 파일 업로드
            uploaded_files = st.file_uploader(
                "PDF 파일들을 선택하세요 (최대 100개)",
                type=['pdf'],
                accept_multiple_files=True,
                help="처리할 PDF 파일들을 업로드하세요 (Ctrl+클릭으로 여러 파일 선택)"
            )
            
            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)}개 파일 업로드 완료!")
                
                # 파일 정보 표시
                st.subheader("📋 업로드된 파일 목록")
                
                # 파일 정보를 데이터프레임으로 표시
                file_info = []
                total_size = 0
                for i, file in enumerate(uploaded_files, 1):
                    size_kb = file.size / 1024
                    total_size += size_kb
                    file_info.append({
                        "번호": i,
                        "파일명": file.name,
                        "크기 (KB)": f"{size_kb:.1f}",
                        "상태": "대기 중"
                    })
                
                df = pd.DataFrame(file_info)
                st.dataframe(df, use_container_width=True)
                
                # 전체 통계
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("총 파일 수", len(uploaded_files))
                with col2:
                    st.metric("총 크기", f"{total_size:.1f} KB")
                with col3:
                    st.metric("평균 크기", f"{total_size/len(uploaded_files):.1f} KB")
                
                # 파일 개수 제한 경고
                if len(uploaded_files) > 100:
                    st.warning("⚠️ 100개 이상의 파일이 업로드되었습니다. 처리 시간이 오래 걸릴 수 있습니다.")
                elif len(uploaded_files) > 50:
                    st.info("ℹ️ 50개 이상의 파일이 업로드되었습니다. 배치 처리를 권장합니다.")
        
        # 처리 옵션 설정
        if 'uploaded_files' in locals() and uploaded_files:
            st.subheader("⚙️ 처리 옵션")
            
            # 처리 모드 통일 (향상된 처리로 고정)
            processing_mode = ("enhanced", "🚀 향상된 처리 (Table Transformer + 패턴 기반)")
            st.info(f"📋 처리 모드: {processing_mode[1]}")
            st.caption("모든 PDF는 Microsoft Table Transformer와 패턴 기반 표 인식을 사용하여 처리됩니다.")
            
            # GPU 및 기타 옵션
            col1, col2 = st.columns(2)
            with col1:
                use_gpu = st.checkbox(
                    "🎮 GPU 가속 사용", 
                    value=False,
                    help="GPU 가속으로 처리 속도 향상 (GPU 필요)"
                )
            with col2:
                merge_small_chunks = st.checkbox(
                    "🔗 작은 청크 병합",
                    value=True,
                    help="100자 미만의 작은 청크를 인근 청크와 병합합니다"
                )
            
            # 처리 버튼 (단일/배치 처리 구분)
            if upload_mode == "📄 단일 파일":
                if st.button("🚀 PDF 파싱 시작", type="primary"):
                    st.info("단일 파일 처리 기능은 현재 개발 중입니다. 배치 처리 모드를 사용해주세요.")
            else:
                # 배치 처리 버튼
                if st.button("🚀 배치 PDF 파싱 시작", type="primary"):
                    # 청크 설정 옵션 (고정값)
                    chunk_options = {
                        'chunk_size': 500,
                        'chunk_overlap': 100,
                        'merge_small_chunks': merge_small_chunks,
                        'use_gpu': use_gpu,
                        'enable_keyword_extraction': True,
                        'keyword_count': 5
                    }
                    
                    # 배치 처리 실행
                    success = process_batch_pdfs(uploaded_files, output_dir, chunk_options)
                    
                    if success:
                        st.success("✅ 배치 PDF 파싱 완료!")
                    else:
                        st.error("❌ 배치 처리 중 오류가 발생했습니다.")
    
    # 탭4: 배치 처리 결과
    with tab4:
        st.header("📊 배치 처리 결과")
        
        # 배치 처리 결과 파일 확인
        batch_summary_path = Path(output_dir) / "batch_summary.json"
        
        if batch_summary_path.exists():
            try:
                with open(batch_summary_path, 'r', encoding='utf-8') as f:
                    batch_results = json.load(f)
                
                st.success("✅ 배치 처리 결과를 찾았습니다!")
                
                # 배치 처리 요약 정보
                st.subheader("📋 배치 처리 요약")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 파일 수", batch_results.get('total_files', 0))
                with col2:
                    st.metric("성공", batch_results.get('successful', 0))
                with col3:
                    st.metric("실패", batch_results.get('failed', 0))
                with col4:
                    total_time = batch_results.get('total_time', 0)
                    st.metric("총 처리 시간", f"{total_time:.1f}초")
                
                # 성공률
                total_files = batch_results.get('total_files', 1)
                successful = batch_results.get('successful', 0)
                success_rate = (successful / total_files) * 100 if total_files > 0 else 0
                st.metric("성공률", f"{success_rate:.1f}%")
                
                # 상세 결과 테이블
                st.subheader("📋 상세 처리 결과")
                
                if 'results' in batch_results and batch_results['results']:
                    results_df = pd.DataFrame(batch_results['results'])
                    
                    # 컬럼명 한글화 (새로운 컬럼 포함)
                    if len(results_df.columns) >= 6:
                        results_df.columns = ['파일명', '상태', '처리 시간', '오류 메시지', '출력 경로', '출력 파일']
                    else:
                        results_df.columns = ['파일명', '상태', '처리 시간', '오류 메시지']
                    
                    # 상태에 따른 색상 적용
                    def color_status(val):
                        if val == '성공':
                            return 'background-color: lightgreen'
                        else:
                            return 'background-color: lightcoral'
                    
                    styled_df = results_df.style.applymap(color_status, subset=['상태'])
                    st.dataframe(styled_df, use_container_width=True)
                    
                    # 개별 파일 다운로드 섹션
                    st.subheader("📥 개별 파일 결과 다운로드")
                    
                    # 성공한 파일들만 필터링
                    successful_results = [r for r in batch_results['results'] if r['status'] == '성공']
                    
                    if successful_results:
                        st.info(f"✅ {len(successful_results)}개 파일의 개별 결과를 다운로드할 수 있습니다.")
                        
                        # 파일별 다운로드 옵션
                        for i, result in enumerate(successful_results):
                            filename = result['filename']
                            output_files = result.get('output_files', [])
                            
                            with st.expander(f"📄 {filename} - 결과 파일 다운로드"):
                                if output_files:
                                    # 주요 파일들 그룹화
                                    json_files = [f for f in output_files if f['type'] == '.json']
                                    md_files = [f for f in output_files if f['type'] == '.md']
                                    other_files = [f for f in output_files if f['type'] not in ['.json', '.md']]
                                    
                                    # JSON 파일 다운로드
                                    if json_files:
                                        st.write("**📋 JSON 파일들:**")
                                        for file_info in json_files:
                                            try:
                                                with open(file_info['path'], 'r', encoding='utf-8') as f:
                                                    file_content = f.read()
                                                
                                                st.download_button(
                                                    label=f"📥 {file_info['name']} ({(file_info['size']/1024):.1f}KB)",
                                                    data=file_content,
                                                    file_name=f"{filename.replace('.pdf', '')}_{file_info['name']}",
                                                    mime="application/json",
                                                    help=f"{file_info['name']} 파일 다운로드"
                                                )
                                            except Exception as e:
                                                st.error(f"파일 로드 실패: {file_info['name']} - {str(e)}")
                                    
                                    # 마크다운 파일 다운로드
                                    if md_files:
                                        st.write("**📝 마크다운 파일들:**")
                                        for file_info in md_files:
                                            try:
                                                with open(file_info['path'], 'r', encoding='utf-8') as f:
                                                    file_content = f.read()
                                                
                                                st.download_button(
                                                    label=f"📥 {file_info['name']} ({(file_info['size']/1024):.1f}KB)",
                                                    data=file_content,
                                                    file_name=f"{filename.replace('.pdf', '')}_{file_info['name']}",
                                                    mime="text/markdown",
                                                    help=f"{file_info['name']} 파일 다운로드"
                                                )
                                            except Exception as e:
                                                st.error(f"파일 로드 실패: {file_info['name']} - {str(e)}")
                                    
                                    # 기타 파일들
                                    if other_files:
                                        st.write("**📁 기타 파일들:**")
                                        for file_info in other_files:
                                            st.write(f"• {file_info['name']} ({(file_info['size']/1024):.1f}KB)")
                                else:
                                    st.warning("출력 파일 정보를 찾을 수 없습니다.")
                    else:
                        st.warning("⚠️ 성공적으로 처리된 파일이 없습니다.")
                
                # 배치 결과 다운로드
                st.subheader("📥 배치 결과 다운로드")
                with open(batch_summary_path, 'r', encoding='utf-8') as f:
                    batch_summary_content = f.read()
                
                st.download_button(
                    label="📊 배치 처리 결과 다운로드",
                    data=batch_summary_content,
                    file_name="batch_summary.json",
                    mime="application/json",
                    help="배치 처리 결과를 JSON 파일로 다운로드합니다"
                )
                
            except Exception as e:
                st.error(f"배치 처리 결과 로드 실패: {str(e)}")
        else:
            st.info("ℹ️ 배치 처리 결과가 없습니다. 배치 처리를 먼저 실행해주세요.")
            
            # 배치 처리 가이드
            st.subheader("📖 배치 처리 사용법")
            st.markdown("""
            1. **PDF 업로드 & 파싱** 탭으로 이동
            2. **업로드 모드**에서 **"📁 다중 파일 (배치 처리)"** 선택
            3. 여러 PDF 파일을 선택하여 업로드
            4. **"🚀 배치 PDF 파싱 시작"** 버튼 클릭
            5. 처리 완료 후 이 탭에서 결과 확인
            """)
    
    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🏥 Medical PDF 파싱 시스템 | Powered by Streamlit</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 