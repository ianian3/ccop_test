# app/services/legal_rag_service.py
"""
법률 RAG 서비스 - ChromaDB 기반 법률 문서 검색 및 자문 시스템
OpenAI text-embedding-3-small 모델 사용
"""
import os
import hashlib
from typing import List, Dict, Optional, Tuple
from flask import current_app

# ChromaDB
import chromadb
from chromadb.config import Settings

# PDF Processing
from pypdf import PdfReader

# OpenAI for embeddings and response generation
from openai import OpenAI


class LegalRAGService:
    """법률 문서 기반 RAG 서비스 (OpenAI 임베딩 사용)"""
    
    _client = None
    _collection = None
    _openai_client = None
    
    # 청크 설정
    CHUNK_SIZE = 500  # 문자 수
    CHUNK_OVERLAP = 50
    
    # 임베딩 모델 설정
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    
    @classmethod
    def get_chroma_client(cls):
        """ChromaDB 클라이언트 초기화"""
        if cls._client is None:
            # 데이터 저장 경로 (Docker: /app/chroma_data, Local: ./chroma_data)
            persist_dir = os.environ.get(
                'CHROMA_DATA_DIR', 
                os.path.join(os.getcwd(), "chroma_data")
            )
            os.makedirs(persist_dir, exist_ok=True)
            
            cls._client = chromadb.PersistentClient(path=persist_dir)
        return cls._client
    
    @classmethod
    def get_collection(cls):
        """법률 문서 컬렉션 가져오기 (OpenAI 임베딩용)"""
        if cls._collection is None:
            client = cls.get_chroma_client()
            # 기존 컬렉션 삭제 후 새로 생성 (임베딩 모델 변경 시)
            try:
                # OpenAI 임베딩을 사용하므로 embedding_function 없이 생성
                cls._collection = client.get_or_create_collection(
                    name="legal_documents_openai",
                    metadata={
                        "description": "법률 및 판례 문서 컬렉션 (OpenAI Embedding)",
                        "embedding_model": cls.EMBEDDING_MODEL
                    }
                )
            except Exception:
                cls._collection = client.get_collection(name="legal_documents_openai")
        return cls._collection
    
    @classmethod
    def get_openai_client(cls):
        """OpenAI 클라이언트 (싱글톤)"""
        if cls._openai_client is None:
            api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
            cls._openai_client = OpenAI(api_key=api_key)
        return cls._openai_client
    
    @classmethod
    def _get_embedding(cls, text: str) -> List[float]:
        """OpenAI 임베딩 생성"""
        client = cls.get_openai_client()
        response = client.embeddings.create(
            model=cls.EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    
    @classmethod
    def _get_embeddings_batch(cls, texts: List[str]) -> List[List[float]]:
        """OpenAI 배치 임베딩 생성 (비용 효율적)"""
        client = cls.get_openai_client()
        response = client.embeddings.create(
            model=cls.EMBEDDING_MODEL,
            input=texts
        )
        # 순서 보장을 위해 index 기준 정렬
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]
    
    @classmethod
    def _chunk_text(cls, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + cls.CHUNK_SIZE
            chunk = text[start:end]
            
            # 문장 끝에서 자르기 시도
            if end < text_length:
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                cut_point = max(last_period, last_newline)
                if cut_point > cls.CHUNK_SIZE // 2:
                    chunk = chunk[:cut_point + 1]
                    end = start + cut_point + 1
            
            chunks.append(chunk.strip())
            start = end - cls.CHUNK_OVERLAP
        
        return [c for c in chunks if c]  # 빈 청크 제거
    
    @classmethod
    def add_pdf(cls, file, filename: str) -> Tuple[bool, str, int]:
        """
        PDF 파일을 파싱하여 벡터 DB에 저장 (OpenAI 임베딩 사용)
        
        Returns:
            (success, message, chunk_count)
        """
        try:
            # PDF 읽기
            reader = PdfReader(file)
            full_text = ""
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            if not full_text.strip():
                return False, "PDF에서 텍스트를 추출할 수 없습니다.", 0
            
            # 청킹
            chunks = cls._chunk_text(full_text)
            if not chunks:
                return False, "텍스트 청킹 실패", 0
            
            # OpenAI 임베딩 생성 (배치)
            embeddings = cls._get_embeddings_batch(chunks)
            
            # 문서 ID 생성 (중복 방지)
            doc_id = hashlib.md5(filename.encode()).hexdigest()[:8]
            
            # ChromaDB에 저장 (임베딩 직접 제공)
            collection = cls.get_collection()
            
            ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
            metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]
            
            collection.add(
                embeddings=embeddings,
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
            
            return True, f"'{filename}' 업로드 완료 (OpenAI 임베딩)", len(chunks)
            
        except Exception as e:
            return False, f"PDF 처리 오류: {str(e)}", 0
    
    @classmethod
    def query(cls, question: str, n_results: int = 5) -> Dict:
        """
        법률 질의응답 (OpenAI 임베딩 사용)
        
        Args:
            question: 사용자 질문
            n_results: 검색할 관련 문서 수
            
        Returns:
            {
                "answer": "AI 생성 답변",
                "sources": [{"content": "...", "source": "filename"}],
                "success": True/False
            }
        """
        try:
            collection = cls.get_collection()
            
            # 질문을 OpenAI 임베딩으로 변환
            question_embedding = cls._get_embedding(question)
            
            # 관련 문서 검색 (임베딩 기반)
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return {
                    "answer": "관련 법률 문서가 없습니다. 먼저 법률 PDF를 업로드해주세요.",
                    "sources": [],
                    "success": False
                }
            
            # 컨텍스트 구성
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            context = "\n\n---\n\n".join([
                f"[출처: {meta['source']}]\n{doc}"
                for doc, meta in zip(documents, metadatas)
            ])
            
            # GPT로 답변 생성
            client = cls.get_openai_client()
            
            system_prompt = """당신은 수사관을 돕는 법률 자문 AI입니다.
제공된 법률 문서를 기반으로 정확하고 실용적인 법률 자문을 제공하세요.

답변 형식:
1. 📖 관련 법률: 적용 가능한 법조항
2. ⚖️ 법적 해석: 해당 상황에 대한 법적 분석
3. 💡 수사 권고: 실무적 조언

중요: 제공된 문서에 없는 내용은 추측하지 마세요."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""질문: {question}

참고 법률 문서:
{context}

위 문서를 기반으로 답변해주세요."""}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # 출처 정보 정리
            sources = [
                {"content": doc[:200] + "..." if len(doc) > 200 else doc, "source": meta['source']}
                for doc, meta in zip(documents, metadatas)
            ]
            
            return {
                "answer": answer,
                "sources": sources,
                "success": True
            }
            
        except Exception as e:
            return {
                "answer": f"오류 발생: {str(e)}",
                "sources": [],
                "success": False
            }
    
    @classmethod
    def get_documents(cls) -> List[Dict]:
        """업로드된 문서 목록 조회"""
        try:
            collection = cls.get_collection()
            
            # 모든 메타데이터 가져오기
            all_data = collection.get()
            
            if not all_data['metadatas']:
                return []
            
            # 문서별로 그룹화
            doc_stats = {}
            for meta in all_data['metadatas']:
                source = meta.get('source', 'Unknown')
                if source not in doc_stats:
                    doc_stats[source] = {"name": source, "chunks": 0}
                doc_stats[source]["chunks"] += 1
            
            return list(doc_stats.values())
            
        except Exception as e:
            return []
    
    @classmethod
    def delete_document(cls, filename: str) -> Tuple[bool, str]:
        """문서 삭제"""
        try:
            collection = cls.get_collection()
            doc_id = hashlib.md5(filename.encode()).hexdigest()[:8]
            
            # 해당 문서의 모든 청크 ID 찾기
            all_data = collection.get()
            ids_to_delete = [
                id for id, meta in zip(all_data['ids'], all_data['metadatas'])
                if meta.get('source') == filename
            ]
            
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                return True, f"'{filename}' 삭제 완료"
            else:
                return False, "문서를 찾을 수 없습니다."
                
        except Exception as e:
            return False, f"삭제 오류: {str(e)}"

    # ============================================
    # LegalGraphRAG 확장 메서드 (Phase 2)
    # ============================================

    @classmethod
    def query_with_context(cls, question: str, case_id: str, graph_path: str, n_results: int = 5) -> Dict:
        """
        그래프 맥락을 반영한 법률 질의 (LegalGraphRAG)
        
        Args:
            question: 사용자 질문
            case_id: 사건 번호
            graph_path: 그래프 경로
            n_results: 검색할 관련 문서 수
            
        Returns:
            {
                "answer": "AI 생성 답변 (맥락 반영)",
                "case_context": {...},
                "evidence_analysis": {...},
                "prosecution_readiness": {...},
                "sources": [...]
            }
        """
        from app.services.graph_context_extractor import GraphContextExtractor
        
        print(f"▶ [LegalGraphRAG] 그래프 맥락 기반 질의 시작: {case_id}")
        
        try:
            # 1. 그래프 맥락 추출
            context = GraphContextExtractor.extract_case_context(case_id, graph_path)
            
            # 2. 쿼리 확장 (맥락 반영)
            enhanced_question = cls._enhance_query_with_context(question, context)
            
            # 3. 관련 법률 문서 검색
            collection = cls.get_collection()
            question_embedding = cls._get_embedding(enhanced_question)
            
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=n_results
            )
            
            # 문서가 없는 경우 처리
            documents = []
            metadatas = []
            if results['documents'] and results['documents'][0]:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0]
            
            # 4. 기소 준비도 평가
            prosecution_readiness = GraphContextExtractor.get_prosecution_readiness(context)
            
            # 5. 맥락 인식 답변 생성
            answer = cls._generate_context_aware_answer(
                question, context, documents, metadatas, prosecution_readiness
            )
            
            # 6. 출처 정보 정리
            sources = []
            for doc, meta in zip(documents, metadatas):
                sources.append({
                    "content": doc[:200] + "..." if len(doc) > 200 else doc,
                    "source": meta.get('source', 'Unknown')
                })
            
            return {
                "answer": answer,
                "case_context": {
                    "case_id": context["case_id"],
                    "crime_type": context["crime_type"],
                    "pattern_confidence": context["pattern_confidence"],
                    "completeness_score": context["completeness_score"],
                    "graph_summary": context["graph_summary"]
                },
                "evidence_analysis": {
                    "confirmed": [
                        {"type": e["type"], "name": e["name"], "status": e["status"]}
                        for e in context["evidence_nodes"]
                    ],
                    "missing": context["missing_evidence"]
                },
                "applicable_laws": context["applicable_laws"],
                "prosecution_readiness": prosecution_readiness,
                "sources": sources,
                "success": True
            }
            
        except Exception as e:
            print(f"   ⚠️ LegalGraphRAG 오류: {e}")
            return {
                "answer": f"그래프 맥락 분석 중 오류 발생: {str(e)}",
                "case_context": {},
                "evidence_analysis": {},
                "prosecution_readiness": {},
                "sources": [],
                "success": False
            }

    @classmethod
    def _enhance_query_with_context(cls, question: str, context: dict) -> str:
        """맥락 기반 쿼리 확장"""
        
        crime_type = context.get("crime_type", "")
        evidence_nodes = context.get("evidence_nodes", [])
        applicable_laws = context.get("applicable_laws", {})
        
        # 쿼리에 맥락 정보 추가
        enhanced_parts = [question]
        
        if crime_type and crime_type != "미확인":
            enhanced_parts.append(f"범죄 유형: {crime_type}")
        
        if evidence_nodes:
            evidence_names = [e["name"] for e in evidence_nodes]
            enhanced_parts.append(f"확보된 증거: {', '.join(evidence_names)}")
        
        primary_laws = applicable_laws.get("primary", [])
        if primary_laws:
            enhanced_parts.append(f"관련 법률: {', '.join(primary_laws[:3])}")
        
        return " ".join(enhanced_parts)

    @classmethod
    def _generate_context_aware_answer(cls, question: str, context: dict, 
                                       documents: list, metadatas: list,
                                       prosecution_readiness: dict) -> str:
        """맥락 인식 답변 생성"""
        
        client = cls.get_openai_client()
        
        # 법률 문서 컨텍스트
        doc_context = ""
        if documents:
            doc_context = "\n\n---\n\n".join([
                f"[출처: {meta.get('source', 'Unknown')}]\n{doc}"
                for doc, meta in zip(documents, metadatas)
            ])
        
        # 증거 현황
        evidence_summary = ""
        for e in context.get("evidence_nodes", []):
            evidence_summary += f"- {e['name']}: {e['status']} (입증: {', '.join(e['proves'][:2])})\n"
        
        missing_evidence = context.get("missing_evidence", [])
        missing_summary = ""
        for m in missing_evidence[:3]:
            missing_summary += f"- {m.get('description', m.get('type', ''))}: ⚠️ 누락\n"
        
        # 적용 법률
        laws = context.get("applicable_laws", {})
        primary_laws = laws.get("primary", [])
        
        system_prompt = """당신은 사이버범죄 수사를 지원하는 법률 AI 자문관입니다.
사건 그래프 분석 결과와 법률 문서를 바탕으로 맥락에 맞는 법률 자문을 제공하세요.

답변 형식:
📖 적용 법률: 이 사건에 적용 가능한 법조항 (1-2개)
⚖️ 증거 분석: 확보된 증거의 법적 의미
💡 수사 권고: 추가 필요한 증거 및 우선순위
📊 기소 가능성: 현재 상태 평가

중요:
- 사건 맥락을 반드시 반영하세요
- 확보/누락 증거를 명확히 구분하세요
- 실행 가능한 구체적 조언을 제공하세요"""

        user_prompt = f"""[사건 정보]
- 사건번호: {context.get('case_id', '미상')}
- 범죄 유형: {context.get('crime_type', '미확인')} (신뢰도: {context.get('pattern_confidence', 0)*100:.1f}%)
- 증거 완성도: {context.get('completeness_score', 0)*100:.1f}%

[확보된 증거]
{evidence_summary if evidence_summary else '없음'}

[누락된 증거]
{missing_summary if missing_summary else '없음'}

[적용 가능 법률]
{chr(10).join(primary_laws) if primary_laws else '분석 중'}

[기소 준비도]
- 점수: {prosecution_readiness.get('prosecution_score', 0)*100:.1f}%
- 상태: {prosecution_readiness.get('status', '평가 중')}

[참고 법률 문서]
{doc_context if doc_context else '업로드된 법률 문서 없음'}

[수사관 질문]
{question}

위 정보를 바탕으로 법률 자문을 제공하세요."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"답변 생성 실패: {str(e)}"

