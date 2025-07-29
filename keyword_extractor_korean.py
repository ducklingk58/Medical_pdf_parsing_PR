#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한글 불용어 제거 KeyBERT 키워드 추출기
JSON 파일의 각 청크에서 한글 불용어를 제거하고 KeyBERT로 키워드를 추출
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import re
from collections import Counter

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KoreanKeywordExtractor:
    """한글 불용어 제거 KeyBERT 키워드 추출기"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        키워드 추출기 초기화
        
        Args:
            model_name: 사용할 sentence transformer 모델명
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"KeyBERT 모델 로딩 중: {model_name}")
        
        try:
            # Sentence Transformer 모델 로드
            from sentence_transformers import SentenceTransformer
            sentence_model = SentenceTransformer(model_name)
            
            # KeyBERT 초기화
            from keybert import KeyBERT
            self.keybert = KeyBERT(model=sentence_model)
            self.logger.info("✅ KeyBERT 모델 로딩 완료")
            
        except ImportError as e:
            self.logger.error(f"❌ KeyBERT 모듈 import 실패: {e}")
            self.keybert = None
        except Exception as e:
            self.logger.error(f"❌ 모델 로딩 실패: {e}")
            self.keybert = None
    
    def get_korean_stopwords(self) -> set:
        """
        한글 불용어 리스트 반환
        
        Returns:
            한글 불용어 집합
        """
        return {
            "정보", "내용", "사항", "기준", "설정", "사용", "적용", "대상", "요구", "관리", "정의",
            "절차", "제공", "중요", "필수", "조치", "방법", "형태", "작성", "필요", "경우", "확인",
            "관련", "제품", "구성", "성분", "문서", "항목", "시행", "검토", "수행", "제출", "예시",
            "설명", "진행", "이용", "목적", "요약", "내용", "검사", "조건", "한계", "형식", "기재",
            "근거", "항목", "자료", "실시", "유형", "종류", "방법", "절차", "시기", "형태", "대응",
            "유무", "단계", "포함", "이유", "표기", "유지", "기간", "구분", "정도", "특성", "활용",
            # 추가 한글 불용어
            "이", "가", "을", "를", "의", "에", "로", "으로", "와", "과", "도", "만", "은", "는",
            "그", "이", "저", "우리", "그들", "이들", "저들", "것", "수", "등", "및", "또는",
            "그리고", "하지만", "그러나", "또한", "있", "하", "되", "들", "보", "않", "없", "나",
            "사람", "주", "아니", "같", "때", "년", "한", "지", "대하", "오", "말", "일", "그렇", "위하",
            "위", "아래", "앞", "뒤", "안", "밖", "속", "밖", "사이", "중간", "가운데", "양쪽",
            "모든", "전체", "일부", "부분", "각", "개별", "개인", "단체", "집단", "조직", "기관",
            "회사", "기업", "단체", "협회", "조합", "연합", "연맹", "동맹", "제휴", "협력", "공조",
            "상호", "양자", "다자", "일방", "쌍방", "상대", "반대", "대립", "대조", "비교", "대비",
            "유사", "동일", "같은", "다른", "차이", "구별", "분별", "식별", "판별", "구분", "분류",
            "정렬", "배열", "배치", "배분", "분배", "할당", "지정", "선정", "선택", "결정", "판단",
            "의견", "생각", "관점", "입장", "태도", "자세", "마음", "심정", "감정", "느낌", "인상",
            "평가", "판가", "가치", "의미", "중요성", "필요성", "당위성", "정당성", "합리성", "적절성"
        }
    
    def clean_text(self, text: str) -> str:
        """
        텍스트 전처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            전처리된 텍스트
        """
        # 특수문자 제거 (한글, 영문, 숫자, 공백만 유지)
        cleaned = re.sub(r'[^\w\s가-힣]', ' ', text)
        # 연속된 공백을 하나로
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()
    
    def contains_stopword(self, keyword: str, stopwords: set) -> bool:
        """
        키워드에 불용어가 포함되어 있는지 확인
        
        Args:
            keyword: 키워드
            stopwords: 불용어 집합
            
        Returns:
            불용어 포함 여부
        """
        # 키워드를 단어로 분리
        words = keyword.split()
        
        # 각 단어가 불용어에 포함되어 있는지 확인
        for word in words:
            if word in stopwords:
                return True
        
        # 키워드 전체가 불용어에 포함되어 있는지 확인
        if keyword in stopwords:
            return True
        
        return False
    
    def extract_keywords_without_stopwords(self, text: str, top_k: int = 5) -> List[str]:
        """
        한글 불용어를 제거하고 KeyBERT로 키워드 추출
        
        Args:
            text: 키워드를 추출할 텍스트
            top_k: 추출할 키워드 개수 (기본값: 5)
            
        Returns:
            추출된 키워드 리스트
        """
        try:
            if self.keybert is None:
                # KeyBERT가 없으면 기본 키워드 추출 사용
                return self.extract_fallback_keywords(text, top_k)
            
            # 텍스트 전처리
            cleaned_text = self.clean_text(text)
            
            if len(cleaned_text) < 10:  # 너무 짧은 텍스트는 기본 키워드 추출
                return self.extract_fallback_keywords(text, top_k)
            
            # 한글 불용어 가져오기
            stopwords = self.get_korean_stopwords()
            
            # KeyBERT로 키워드 후보 추출 (더 많은 후보 생성)
            keyword_candidates = self.keybert.extract_keywords(
                cleaned_text,
                keyphrase_ngram_range=(1, 2),  # 1-2단어 조합
                stop_words=None,
                top_k=15,  # 최대 15개 후보 생성
                diversity=0.8  # 다양성 보장
            )
            
            if not keyword_candidates:
                return self.extract_fallback_keywords(text, top_k)
            
            # 불용어가 포함되지 않은 키워드만 필터링
            filtered_keywords = []
            for keyword, score in keyword_candidates:
                if not self.contains_stopword(keyword, stopwords):
                    filtered_keywords.append(keyword)
            
            # 상위 top_k개 키워드 반환
            return filtered_keywords[:top_k]
            
        except Exception as e:
            self.logger.error(f"키워드 추출 실패: {e}")
            return self.extract_fallback_keywords(text, top_k)
    
    def extract_fallback_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        KeyBERT 실패 시 사용할 기본 키워드 추출
        
        Args:
            text: 키워드를 추출할 텍스트
            top_k: 추출할 키워드 개수
            
        Returns:
            추출된 키워드 리스트
        """
        # 의료 관련 키워드 패턴
        medical_keywords = [
            'PSUR', '안전성', '정보', '보고', '허가', '평가', '의료기기', '의약품',
            '품질', '관리', '시정', '예방', '조치', '심사', '절차', '제조업체',
            '식약처', '가이드라인', '서류', '첨단바이오의약품', '시판', '품질평가',
            '생물학적', '특성', '제조', '공정', '복잡성', 'GMP', '시스템',
            '개선', '위험', '방지', '기술문서', '임상데이터', '유효성', '심사기관',
            '프로파일', '모니터링', '도구', '인증', '신고', '고려사항', '방법',
            '접근', '과정', '입증', '요구사항', '자료', '보완', '검증', '승인',
            '등록', '변경', '폐지', '취소', '정지', '제한', '조건', '기간',
            '범위', '대상', '기준', '규정', '지침', '매뉴얼', '절차서', '표준',
            '규격', '사양', '성능', '기능', '효과', '결과', '분석', '검토',
            '검사', '시험', '측정', '계산', '산출', '도출', '결정', '판단',
            '의견', '제안', '권고', '지시', '명령', '요청', '신청', '제출',
            '접수', '처리', '검토', '심의', '의결', '결정', '통보', '고지',
            '공고', '발표', '공개', '제공', '교부', '수령', '접수', '처리',
            # 압력분산 매트리스 관련 키워드
            '압력분산', '매트리스', '욕창', '예방', '피부', '손상', '피하조직',
            '압박', '분산', '체중', '지지', '표면', '재질', '구조', '설계',
            '안정성', '내구성', '편안함', '지지력', '분산력', '압력', '분포'
        ]
        
        # 텍스트에서 키워드 찾기
        found_keywords = []
        for keyword in medical_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        # 상위 top_k개만 반환
        return found_keywords[:top_k]
    
    def process_json_file(self, input_file: str, output_file: str = None) -> str:
        """
        JSON 파일의 모든 청크에 키워드 추가
        
        Args:
            input_file: 입력 JSON 파일 경로
            output_file: 출력 JSON 파일 경로 (None이면 자동 생성)
            
        Returns:
            출력 파일 경로
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_file}")
        
        # 출력 파일명 설정
        if output_file is None:
            output_path = input_path.parent / "with_keywords.json"
        else:
            output_path = Path(output_file)
        
        self.logger.info(f"📖 JSON 파일 로딩: {input_file}")
        
        try:
            # JSON 파일 로드
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValueError("JSON 파일은 배열 형태여야 합니다.")
            
            self.logger.info(f"📊 총 {len(data)}개 청크 처리 시작")
            
            # 각 청크에 키워드 추가
            processed_data = []
            for i, chunk in enumerate(data):
                if i % 10 == 0:  # 진행상황 로그
                    self.logger.info(f"처리 중... {i+1}/{len(data)}")
                
                # 청크 복사
                processed_chunk = chunk.copy()
                
                # text 필드 확인
                if 'text' not in processed_chunk:
                    self.logger.warning(f"청크 {i}에 'text' 필드가 없습니다.")
                    processed_chunk['keywords'] = []
                    processed_data.append(processed_chunk)
                    continue
                
                # 키워드 추출 (한글 불용어 제거)
                text = processed_chunk['text']
                keywords = self.extract_keywords_without_stopwords(text, top_k=5)
                
                # 키워드 필드 추가
                processed_chunk['keywords'] = keywords
                processed_data.append(processed_chunk)
            
            # 결과 저장
            self.logger.info(f"💾 결과 저장: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info("✅ 키워드 추출 완료!")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"❌ 처리 실패: {e}")
            raise

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='한글 불용어 제거 KeyBERT 키워드 추출')
    parser.add_argument('--input', '-i', required=True, help='입력 JSON 파일 경로')
    parser.add_argument('--output', '-o', help='출력 JSON 파일 경로 (선택사항)')
    parser.add_argument('--model', '-m', default='all-MiniLM-L6-v2', help='사용할 모델명')
    parser.add_argument('--top-k', '-k', type=int, default=5, help='추출할 키워드 개수')
    
    args = parser.parse_args()
    
    try:
        # 키워드 추출기 초기화
        extractor = KoreanKeywordExtractor(model_name=args.model)
        
        # 파일 처리
        output_file = extractor.process_json_file(args.input, args.output)
        
        print(f"\n🎉 키워드 추출 완료!")
        print(f"📁 출력 파일: {output_file}")
        
    except Exception as e:
        logger.error(f"실행 실패: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 