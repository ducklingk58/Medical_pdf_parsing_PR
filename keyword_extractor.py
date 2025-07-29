#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
키워드 추출기
JSON 파일의 각 청크에서 핵심 키워드를 추출하여 새로운 필드로 추가
문서 제목 기준 유사도 기반 키워드 추출
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

class KeywordExtractor:
    """JSON 청크에서 키워드를 추출하는 클래스"""
    
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
    
    def extract_keywords_with_title_similarity(self, text: str, document_title: str, top_k: int = 5) -> List[str]:
        """
        문서 제목 기준 유사도 기반 키워드 추출 (반드시 5개 키워드 보장)
        
        Args:
            text: 키워드를 추출할 텍스트
            document_title: 문서 제목 (유사도 계산 기준)
            top_k: 추출할 키워드 개수 (기본값: 5)
            
        Returns:
            추출된 키워드 리스트 (반드시 top_k개)
        """
        try:
            if self.keybert is None:
                # KeyBERT가 없으면 기본 키워드 추출 사용
                return self.extract_fallback_keywords(text, top_k)
            
            # 텍스트 전처리
            cleaned_text = self.clean_text(text)
            
            if len(cleaned_text) < 10:  # 너무 짧은 텍스트는 기본 키워드 추출
                return self.extract_fallback_keywords(text, top_k)
            
            # 1단계: 문서 제목에서 핵심 키워드 추출
            title_keywords = self.extract_title_keywords(document_title)
            
            # 2단계: KeyBERT로 키워드 후보 추출 (더 많은 후보 생성)
            keyword_candidates = self.keybert.extract_keywords(
                cleaned_text,
                keyphrase_ngram_range=(1, 3),  # 1-3단어 조합
                stop_words=None,
                top_k=50,  # 더 많은 후보 생성
                diversity=0.9  # 다양성 보장
            )
            
            if not keyword_candidates:
                return self.extract_fallback_keywords(text, top_k)
            
            # 3단계: 문서 제목 키워드와의 유사도 계산 및 우선순위 부여
            title_similarities = []
            for keyword, score in keyword_candidates:
                # 키워드와 문서 제목의 유사도 계산
                similarity = self.calculate_title_similarity(keyword, document_title)
                
                # 문서 제목 키워드와의 직접 매칭 점수 추가
                title_match_score = self.calculate_title_keyword_match(keyword, title_keywords)
                
                # 최종 점수: 유사도 + 제목 키워드 매칭 점수
                final_score = similarity + (title_match_score * 0.5)  # 제목 키워드 매칭에 가중치
                
                title_similarities.append((keyword, final_score))
            
            # 4단계: 최종 점수 기준으로 정렬
            title_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # 5단계: 반드시 top_k개 키워드 보장
            selected_keywords = []
            
            # 우선순위가 높은 키워드들 먼저 선택
            for keyword, score in title_similarities:
                if len(selected_keywords) >= top_k:
                    break
                if keyword not in selected_keywords:
                    selected_keywords.append(keyword)
            
            # 만약 top_k개가 안 되면 추가 키워드 추출
            if len(selected_keywords) < top_k:
                additional_keywords = self.extract_additional_keywords(text, selected_keywords, top_k - len(selected_keywords))
                selected_keywords.extend(additional_keywords)
            
            # 최종적으로 top_k개만 반환
            return selected_keywords[:top_k]
            
        except Exception as e:
            self.logger.error(f"키워드 추출 실패: {e}")
            return self.extract_fallback_keywords(text, top_k)
    
    def extract_title_keywords(self, document_title: str) -> List[str]:
        """
        문서 제목에서 핵심 키워드 추출
        
        Args:
            document_title: 문서 제목
            
        Returns:
            제목에서 추출된 핵심 키워드 리스트
        """
        try:
            if self.keybert is None:
                # KeyBERT가 없으면 기본 키워드 추출
                return self.extract_fallback_keywords(document_title, 10)
            
            # 문서 제목에서 키워드 추출
            title_keywords = self.keybert.extract_keywords(
                document_title,
                keyphrase_ngram_range=(1, 3),
                stop_words=None,
                top_k=10,
                diversity=0.8
            )
            
            # 키워드만 추출
            keywords = [keyword for keyword, score in title_keywords]
            return keywords
            
        except Exception as e:
            self.logger.warning(f"제목 키워드 추출 실패: {e}")
            return []
    
    def calculate_title_keyword_match(self, keyword: str, title_keywords: List[str]) -> float:
        """
        키워드와 제목 키워드 간의 직접 매칭 점수 계산
        
        Args:
            keyword: 키워드
            title_keywords: 제목에서 추출된 키워드 리스트
            
        Returns:
            매칭 점수 (0.0 ~ 1.0)
        """
        if not title_keywords:
            return 0.0
        
        # 정확한 매칭
        if keyword in title_keywords:
            return 1.0
        
        # 부분 매칭 (키워드가 제목 키워드에 포함되는 경우)
        keyword_lower = keyword.lower()
        for title_keyword in title_keywords:
            title_keyword_lower = title_keyword.lower()
            
            # 키워드가 제목 키워드에 포함되거나, 제목 키워드가 키워드에 포함되는 경우
            if keyword_lower in title_keyword_lower or title_keyword_lower in keyword_lower:
                return 0.8
        
        # 단어 단위 매칭
        keyword_words = set(keyword_lower.split())
        for title_keyword in title_keywords:
            title_keyword_words = set(title_keyword.lower().split())
            
            # 겹치는 단어가 있는 경우
            intersection = keyword_words.intersection(title_keyword_words)
            if intersection:
                return 0.6 * (len(intersection) / max(len(keyword_words), len(title_keyword_words)))
        
        return 0.0
    
    def calculate_title_similarity(self, keyword: str, document_title: str) -> float:
        """
        키워드와 문서 제목 간의 유사도 계산
        
        Args:
            keyword: 키워드
            document_title: 문서 제목
            
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        try:
            if self.keybert is None:
                return self.calculate_simple_similarity(keyword, document_title)
            
            # KeyBERT를 사용한 의미적 유사도 계산
            embeddings = self.keybert.model.encode([keyword, document_title])
            
            # 코사인 유사도 계산
            from sklearn.metrics.pairwise import cosine_similarity
            similarity_matrix = cosine_similarity([embeddings[0]], [embeddings[1]])
            similarity_score = similarity_matrix[0][0]
            
            return float(similarity_score)
            
        except Exception as e:
            self.logger.warning(f"유사도 계산 실패, 기본 방법 사용: {e}")
            return self.calculate_simple_similarity(keyword, document_title)
    
    def calculate_simple_similarity(self, keyword: str, document_title: str) -> float:
        """
        간단한 유사도 계산 (단어 겹침 기반)
        
        Args:
            keyword: 키워드
            document_title: 문서 제목
            
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        # 텍스트 정리
        keyword_clean = self.clean_text(keyword.lower())
        title_clean = self.clean_text(document_title.lower())
        
        # 단어 분리
        keyword_words = set(keyword_clean.split())
        title_words = set(title_clean.split())
        
        if not keyword_words or not title_words:
            return 0.0
        
        # 겹치는 단어 수 계산
        intersection = keyword_words.intersection(title_words)
        union = keyword_words.union(title_words)
        
        # Jaccard 유사도
        similarity = len(intersection) / len(union) if union else 0.0
        
        return similarity
    
    def extract_fallback_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        KeyBERT 실패 시 사용할 기본 키워드 추출 (반드시 top_k개 보장)
        
        Args:
            text: 키워드를 추출할 텍스트
            top_k: 추출할 키워드 개수
            
        Returns:
            추출된 키워드 리스트 (반드시 top_k개)
        """
        # 의료 관련 키워드 패턴
        medical_keywords = self.get_medical_keywords()
        
        # 텍스트에서 키워드 찾기
        found_keywords = []
        for keyword in medical_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        # 만약 의료 키워드가 부족하면 추가 키워드 추출
        if len(found_keywords) < top_k:
            additional_keywords = self.extract_additional_keywords(text, found_keywords, top_k - len(found_keywords))
            found_keywords.extend(additional_keywords)
        
        # 최종적으로 top_k개만 반환
        return found_keywords[:top_k]
    
    def extract_additional_keywords(self, text: str, existing_keywords: List[str], needed_count: int) -> List[str]:
        """
        추가 키워드 추출 (의미 있는 단어들)
        
        Args:
            text: 원본 텍스트
            existing_keywords: 이미 선택된 키워드들
            needed_count: 추가로 필요한 키워드 개수
            
        Returns:
            추가 키워드 리스트
        """
        try:
            # 텍스트 전처리
            cleaned_text = self.clean_text(text)
            words = cleaned_text.split()
            
            # 2글자 이상의 의미 있는 단어들 필터링
            meaningful_words = []
            for word in words:
                if len(word) >= 2 and word not in existing_keywords:
                    # 불용어 제거
                    if word not in self.get_stop_words():
                        meaningful_words.append(word)
            
            # 단어 빈도 계산
            word_freq = Counter(meaningful_words)
            
            # 빈도순으로 정렬
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            
            # 추가 키워드 선택
            additional_keywords = []
            for word, freq in sorted_words:
                if len(additional_keywords) >= needed_count:
                    break
                if word not in existing_keywords and word not in additional_keywords:
                    additional_keywords.append(word)
            
            # 의료 관련 키워드 사전에서도 추가
            if len(additional_keywords) < needed_count:
                medical_keywords = self.get_medical_keywords()
                for keyword in medical_keywords:
                    if len(additional_keywords) >= needed_count:
                        break
                    if keyword in text and keyword not in existing_keywords and keyword not in additional_keywords:
                        additional_keywords.append(keyword)
            
            return additional_keywords
            
        except Exception as e:
            self.logger.warning(f"추가 키워드 추출 실패: {e}")
            return []
    
    def get_stop_words(self) -> List[str]:
        """한국어 불용어 리스트"""
        return [
            '이', '가', '을', '를', '의', '에', '로', '으로', '와', '과', '도', '만', '은', '는',
            '그', '이', '저', '우리', '그들', '이들', '저들', '것', '수', '등', '및', '또는',
            '그리고', '하지만', '그러나', '또한', '또한', '또한', '또한', '또한', '또한',
            '있', '하', '되', '것', '들', '수', '이', '보', '않', '없', '나', '사람', '주', '아니', '등', '같', '우리', '때', '년', '가', '한', '지', '대하', '오', '말', '일', '그렇', '위하'
        ]
    
    def get_medical_keywords(self) -> List[str]:
        """의료 관련 키워드 사전"""
        return [
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
            '공고', '발표', '공개', '제공', '교부', '수령', '접수', '처리'
        ]
    
    def extract_document_title(self, text_chunks: List[Dict[str, Any]]) -> str:
        """
        텍스트 청크에서 문서 제목 추출
        
        Args:
            text_chunks: 텍스트 청크 리스트
            
        Returns:
            추출된 문서 제목
        """
        # 첫 번째 청크에서 제목 추출 시도
        if text_chunks and len(text_chunks) > 0:
            first_chunk = text_chunks[0]
            
            # metadata에서 heading 확인
            if 'metadata' in first_chunk and 'heading' in first_chunk['metadata']:
                heading = first_chunk['metadata']['heading']
                if heading and len(heading.strip()) > 0:
                    return heading.strip()
            
            # text에서 첫 번째 줄을 제목으로 사용
            if 'text' in first_chunk:
                text = first_chunk['text']
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 5 and len(line) < 100:
                        return line
        
        return "의료기기 가이드라인"
    
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
            output_path = input_path.parent / f"{input_path.stem}_with_keywords.json"
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
            
            # 문서 제목 추출
            document_title = self.extract_document_title(data)
            self.logger.info(f"📋 문서 제목: {document_title}")
            
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
                
                # 키워드 추출 (문서 제목 기준 유사도)
                text = processed_chunk['text']
                keywords = self.extract_keywords_with_title_similarity(text, document_title)
                
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
    
    parser = argparse.ArgumentParser(description='JSON 청크에서 키워드 추출')
    parser.add_argument('--input', '-i', required=True, help='입력 JSON 파일 경로')
    parser.add_argument('--output', '-o', help='출력 JSON 파일 경로 (선택사항)')
    parser.add_argument('--model', '-m', default='all-MiniLM-L6-v2', help='사용할 모델명')
    parser.add_argument('--top-k', '-k', type=int, default=5, help='추출할 키워드 개수')
    
    args = parser.parse_args()
    
    try:
        # 키워드 추출기 초기화
        extractor = KeywordExtractor(model_name=args.model)
        
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