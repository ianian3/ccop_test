import logging
import uuid
import json
from langchain_openai import OpenAIEmbeddings
from flask import current_app
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

class VectorRAGService:
    """
    ChromaDB 기반 Entity Resolution 서비스.
    그래프 내의 핵심 노드(인물, 계좌, 전화번호 등) 속성을 
    Vector DB에 임베딩하여 유사도 검색을 지원합니다.
    """
    
    _chroma_client = None

    @classmethod
    def get_chroma_client(cls):
        """ChromaDB 로컬 클라이언트 지연 싱글톤 반환. Legal RAG와 동일 방식."""
        if cls._chroma_client is None:
            import chromadb
            config = current_app.config
            db_path = config.get('CHROMA_DB_DIR', './data/chromadb')
            cls._chroma_client = chromadb.PersistentClient(path=db_path)
            logger.info(f"VectorRAGService: ChromaDB 연결 완료 (경로: {db_path})")
        return cls._chroma_client

    @classmethod
    def get_embeddings(cls):
        """OpenAI 임베딩 모델 인스턴스 반환"""
        return OpenAIEmbeddings(
            model="text-embedding-3-small", 
            openai_api_key=current_app.config['OPENAI_API_KEY']
        )

    @classmethod
    def build_entity_vectors(cls, graph_path):
        """
        주어진 그래프(graph_path)의 모든 Actor/Evidence 노드를 
        ChromaDB에 벡터화하여 저장합니다.
        (배치 작업 또는 ETL 마지막 단계에서 호출)
        """
        logger.info(f"▶ [VectorRAG] Entity 임베딩 빌드 시작 ({graph_path})")
        
        # 1. 대상 라벨 (검색 대상이 될 만한 엔티티)
        target_labels = ['vt_psn', 'vt_org', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_site', 'vt_case']
        
        conn, cur = GraphService.get_db_connection()
        if not conn:
            logger.error("DB 연결 실패")
            return False
            
        try:
            from app.database import safe_set_graph_path
            safe_set_graph_path(cur, graph_path)
            
            # 컬렉션 획득 (존재하면 삭제 후 재생성하여 초기화)
            client = cls.get_chroma_client()
            collection_name = f"entity_{graph_path}"
            try:
                client.delete_collection(name=collection_name)
            except:
                pass
                
            collection = client.create_collection(
                name=collection_name, 
                metadata={"description": "Graph Entity Search Collection"}
            )
            embeddings_model = cls.get_embeddings()
            
            total_added = 0
            for label in target_labels:
                cur.execute(f"MATCH (n:{label}) RETURN id(n), properties(n)")
                rows = cur.fetchall()
                if not rows: continue
                
                texts = []
                metadatas = []
                ids = []
                
                for r in rows:
                    node_id = str(r[0])
                    props = GraphService.safe_props(r[1])
                    
                    # 검색에 도움이 될 만한 텍스트 구성 (예: "홍길동, 국민은행 110-1111-2222")
                    doc_text = f"라벨: {label}\n"
                    for k, v in props.items():
                        if k in ['name', 'nickname', 'actno', 'bank_name', 'telno', 'ip_addr', 'flnm', 'crime']:
                            doc_text += f"{k}: {v}\n"
                            
                    texts.append(doc_text)
                    metadatas.append({
                        "node_id": node_id, 
                        "label": label, 
                        "props": json.dumps(props, ensure_ascii=False)
                    })
                    ids.append(f"{graph_path}_{label}_{node_id}")
                
                # ChromaDB에 임베딩 및 저장
                if texts:
                    try:
                        # chromadb collection.add automatically uses the client's embedding function if not provided explicitly,
                        # However we want to use our OpenAI embedding. We can generate embeddings and pass them directly.
                        vectors = embeddings_model.embed_documents(texts)
                        collection.add(
                            embeddings=vectors,
                            documents=texts,
                            metadatas=metadatas,
                            ids=ids
                        )
                        total_added += len(texts)
                    except Exception as e:
                        logger.error(f"Error adding vectors for {label}: {e}")
                        
            logger.info(f"▶ [VectorRAG] Entity 빌드 완료. 총 {total_added}개 저장.")
            return True
            
        except Exception as e:
            logger.error(f"VectorRAG Entity Build Failed: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @classmethod
    def semantic_search_entities(cls, keyword, graph_path, limit=3):
        """
        키워드를 기반으로 ChromaDB에서 가장 유사한 Entity를 검색합니다.
        기존 GraphService.search_nodes를 보완/대체하는 하이브리드 RAG 역할.
        """
        try:
            client = cls.get_chroma_client()
            collection_name = f"entity_{graph_path}"
            
            try:
                collection = client.get_collection(name=collection_name)
            except Exception:
                logger.warning(f"Vector Collection '{collection_name}' 이 존재하지 않습니다.")
                return []
                
            embeddings_model = cls.get_embeddings()
            query_vector = embeddings_model.embed_query(keyword)
            
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=limit
            )
            
            entities = []
            if results and results.get('documents'):
                for i in range(len(results['documents'][0])):
                    doc = results['documents'][0][i]
                    meta = results['metadatas'][0][i]
                    # score = results['distances'][0][i] if 'distances' in results else 0
                    
                    entities.append({
                        "node_id": meta.get('node_id'),
                        "label": meta.get('label'),
                        "props": json.loads(meta.get('props', '{}')),
                        "semantic_match": doc
                    })
                    
            return entities
            
        except Exception as e:
            logger.error(f"VectorRAG Search Failed: {e}")
            return []
