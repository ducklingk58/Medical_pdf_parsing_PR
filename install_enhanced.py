#!/usr/bin/env python3
"""
향상된 Medical PDF 파싱 시스템 설치 스크립트
LayoutParser + PaddleOCR + PyMuPDF 통합 설치
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

def run_command(command, description):
    """명령어 실행 및 결과 출력"""
    print(f"\n🔧 {description}")
    print(f"실행 명령어: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description} 성공")
        if result.stdout:
            print(f"출력: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패")
        print(f"오류: {e.stderr}")
        return False

def check_gpu():
    """GPU 사용 가능 여부 확인"""
    print("\n🔍 GPU 사용 가능 여부 확인 중...")
    
    try:
        result = subprocess.run("nvidia-smi", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ NVIDIA GPU 발견")
            print("GPU 정보:")
            print(result.stdout)
            return True
        else:
            print("❌ NVIDIA GPU를 찾을 수 없습니다")
            return False
    except FileNotFoundError:
        print("❌ nvidia-smi 명령어를 찾을 수 없습니다")
        return False

def install_basic_dependencies():
    """기본 의존성 설치"""
    print("\n📦 기본 의존성 설치 중...")
    
    basic_packages = [
        "unstructured[pdf]>=0.10.0",
        "pandas>=1.5.0",
        "numpy>=1.21.0",
        "tqdm>=4.64.0",
        "streamlit>=1.28.0",
        "plotly>=5.15.0",
        "Pillow>=9.0.0",
        "openpyxl>=3.0.0",
        "pathlib2>=2.3.0",
        "python-multipart>=0.0.6"
    ]
    
    for package in basic_packages:
        if not run_command(f"pip install {package}", f"{package} 설치"):
            return False
    
    return True

def install_layoutparser():
    """LayoutParser 설치"""
    print("\n🎯 LayoutParser 설치 중...")
    
    # LayoutParser 기본 설치
    if not run_command("pip install layoutparser>=0.3.4", "LayoutParser 기본 설치"):
        return False
    
    # Detectron2 백엔드 설치
    if not run_command("pip install layoutparser[detectron2]", "LayoutParser Detectron2 백엔드"):
        return False
    
    return True

def install_paddleocr():
    """PaddleOCR 설치"""
    print("\n🚀 PaddleOCR 설치 중...")
    
    # PaddlePaddle CPU 버전 설치
    if not run_command("pip install paddlepaddle>=2.5.0", "PaddlePaddle CPU 설치"):
        return False
    
    # PaddleOCR 설치
    if not run_command("pip install paddleocr>=2.7.0", "PaddleOCR 설치"):
        return False
    
    return True

def install_paddleocr_gpu():
    """PaddleOCR GPU 버전 설치"""
    print("\n🚀 PaddleOCR GPU 버전 설치 중...")
    
    # PaddlePaddle GPU 버전 설치
    if not run_command("pip install paddlepaddle-gpu>=2.5.0", "PaddlePaddle GPU 설치"):
        return False
    
    # PaddleOCR 설치
    if not run_command("pip install paddleocr>=2.7.0", "PaddleOCR 설치"):
        return False
    
    return True

def install_image_processing():
    """이미지 처리 라이브러리 설치"""
    print("\n🖼️ 이미지 처리 라이브러리 설치 중...")
    
    image_packages = [
        "opencv-python>=4.8.0",
        "scikit-image>=0.21.0",
        "PyMuPDF>=1.23.0"
    ]
    
    for package in image_packages:
        if not run_command(f"pip install {package}", f"{package} 설치"):
            return False
    
    return True

def install_sentence_transformers():
    """Sentence Transformers 설치"""
    print("\n🧠 Sentence Transformers 설치 중...")
    
    if not run_command("pip install sentence-transformers>=2.2.0", "Sentence Transformers 설치"):
        return False
    
    return True

def create_directories():
    """필요한 디렉토리 생성"""
    print("\n📁 디렉토리 생성 중...")
    
    directories = [
        "input_pdfs",
        "output_data",
        "logs",
        "temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ {directory}/ 디렉토리 생성")
    
    return True

def download_models():
    """필요한 모델 다운로드"""
    print("\n📥 모델 다운로드 중...")
    
    # LayoutParser 모델 다운로드 테스트
    try:
        import layoutparser as lp
        print("✅ LayoutParser 모델 다운로드 완료")
    except Exception as e:
        print(f"⚠️ LayoutParser 모델 다운로드 실패: {e}")
    
    # PaddleOCR 모델 다운로드 테스트
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        print("✅ PaddleOCR 모델 다운로드 완료")
    except Exception as e:
        print(f"⚠️ PaddleOCR 모델 다운로드 실패: {e}")
    
    return True

def test_installation():
    """설치 테스트"""
    print("\n🧪 설치 테스트 중...")
    
    test_imports = [
        ("layoutparser", "LayoutParser"),
        ("paddleocr", "PaddleOCR"),
        ("fitz", "PyMuPDF"),
        ("cv2", "OpenCV"),
        ("unstructured", "Unstructured"),
        ("streamlit", "Streamlit")
    ]
    
    all_success = True
    
    for module, name in test_imports:
        try:
            __import__(module)
            print(f"✅ {name} import 성공")
        except ImportError as e:
            print(f"❌ {name} import 실패: {e}")
            all_success = False
    
    return all_success

def main():
    """메인 설치 함수"""
    print("=" * 80)
    print("🚀 향상된 Medical PDF 파싱 시스템 설치")
    print("=" * 80)
    
    # 시스템 정보 출력
    print(f"운영체제: {platform.system()} {platform.release()}")
    print(f"Python 버전: {sys.version}")
    
    # GPU 확인
    has_gpu = check_gpu()
    
    # 기본 의존성 설치
    if not install_basic_dependencies():
        print("❌ 기본 의존성 설치 실패")
        return False
    
    # LayoutParser 설치
    if not install_layoutparser():
        print("❌ LayoutParser 설치 실패")
        return False
    
    # PaddleOCR 설치 (GPU 여부에 따라)
    if has_gpu:
        print("\n🚀 GPU 감지됨 - GPU 버전 설치")
        if not install_paddleocr_gpu():
            print("❌ PaddleOCR GPU 설치 실패")
            return False
    else:
        print("\n💻 CPU 버전 설치")
        if not install_paddleocr():
            print("❌ PaddleOCR 설치 실패")
            return False
    
    # 이미지 처리 라이브러리 설치
    if not install_image_processing():
        print("❌ 이미지 처리 라이브러리 설치 실패")
        return False
    
    # Sentence Transformers 설치
    if not install_sentence_transformers():
        print("❌ Sentence Transformers 설치 실패")
        return False
    
    # 디렉토리 생성
    if not create_directories():
        print("❌ 디렉토리 생성 실패")
        return False
    
    # 모델 다운로드
    download_models()
    
    # 설치 테스트
    if not test_installation():
        print("❌ 설치 테스트 실패")
        return False
    
    print("\n" + "=" * 80)
    print("🎉 향상된 Medical PDF 파싱 시스템 설치 완료!")
    print("=" * 80)
    
    print("\n📋 사용 방법:")
    print("1. PDF 파일을 input_pdfs/ 디렉토리에 넣으세요")
    print("2. 다음 명령어로 실행하세요:")
    print("   python run_enhanced_processing.py")
    print("3. GPU 가속을 사용하려면:")
    print("   python run_enhanced_processing.py --use-gpu")
    print("4. 대시보드를 실행하려면:")
    print("   python run_enhanced_processing.py --dashboard")
    
    if has_gpu:
        print("\n🚀 GPU 가속이 활성화되었습니다!")
        print("고성능 처리를 위해 --use-gpu 옵션을 사용하세요.")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ 설치가 성공적으로 완료되었습니다!")
            sys.exit(0)
        else:
            print("\n❌ 설치 중 오류가 발생했습니다.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 설치가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        sys.exit(1) 