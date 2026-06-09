"""
osint_v37_postprocess.py — OSINT V3.7 통합 후처리 모듈

OSINT V3.6 ETL에 V3.7 신규 노드/엣지/속성을 추가하는 후처리 단계를 담당.

신설 단계:
- STEP 7.5a:  site_cluster 노드 생성 (HTML SimHash 군집화)
- STEP 7.5b:  (옵션) pt_cluster 노드 (OSINT는 보통 미사용)
- STEP 8.5a:  belongs_to_campaign 엣지 (vt_site → site_cluster)
- STEP 8.6:   vt_id.is_anonymous 마킹 (wrtr_nm 비식별)

설계 표준:
- 단일 SSOT (KICSCrimeDomainOntology) 참조 — 라벨/엣지/속성 검증
- id_format 메타 부여 — Cross-source sameAs 자동화 기반
- 도메인 메타 'osint' 표시 — DOMAIN_USAGE 일관성

사용:
    python -m app.services.osint_v37_postprocess --graph osint_ontology
    # 또는 OSINT ETL의 STEP 7 이후 호출
"""
import argparse
import hashlib
import logging
import os
import re
from collections import defaultdict
from typing import List, Tuple

import psycopg2
from dotenv import load_dotenv

from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto

load_dotenv()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# SimHash 64-bit (외부 라이브러리 없이 자체 구현 - 추가 의존성 최소화)
# ──────────────────────────────────────────────────────────────────────────────

def _tokenize_html(html: str) -> List[str]:
    """HTML 토큰화 — 태그 + 텍스트 단어 + 속성값(class/id) 가중치 토큰.

    실무에서는 더 정교한 DOM 파싱이 좋지만, 여기선 빠른 정규식 기반.
    """
    if not html:
        return []
    text = re.sub(r'<script[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
    # 태그 이름
    tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)', text)
    # class/id 값
    classes = re.findall(r'(?:class|id)\s*=\s*["\']([^"\']+)["\']', text)
    class_tokens = []
    for c in classes:
        class_tokens.extend(c.split())
    # 텍스트 단어 (소문자, 3글자 이상)
    txt = re.sub(r'<[^>]+>', ' ', text)
    words = [w.lower() for w in re.findall(r'[A-Za-z가-힣]{3,}', txt)]
    return [f"t:{t}" for t in tags] + [f"c:{c}" for c in class_tokens] + words[:500]


def simhash64(tokens: List[str]) -> int:
    """64-bit SimHash."""
    if not tokens:
        return 0
    v = [0] * 64
    for token in tokens:
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest()[:16], 16)
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count('1')


# ──────────────────────────────────────────────────────────────────────────────
# Union-Find (군집화)
# ──────────────────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def clusters(self):
        groups = defaultdict(list)
        for node in self.parent:
            groups[self.find(node)].append(node)
        return list(groups.values())


# ──────────────────────────────────────────────────────────────────────────────
# OSINT V3.7 후처리 클래스
# ──────────────────────────────────────────────────────────────────────────────

class OsintV37Postprocess:
    """OSINT ETL 후처리 — V3.7 신규 노드/엣지/속성 생성.

    호출 순서:
        1. STEP 7 (기존 노드 적재) 완료 후 진입
        2. site_cluster 생성 (HTML SimHash)
        3. belongs_to_campaign 엣지
        4. vt_id.is_anonymous 마킹
    """

    HAMMING_THRESHOLD = 3       # SimHash 군집화 임계값
    MIN_CLUSTER_SIZE = 2        # 군집 최소 멤버 수

    def __init__(self, conn, graph_name: str = 'osint_ontology'):
        self.conn = conn
        self.graph = graph_name
        # SSOT 검증 — V3.7 라벨 존재 확인
        if Onto.get_domain_usage('site_cluster', 'osint') != 'primary':
            raise RuntimeError("V3.7 표준에서 site_cluster의 OSINT 도메인 사용이 'primary'가 아님 — SSOT 점검 필요")
        self.id_fmt_site = Onto.get_id_format('vt_site')['default_format']
        self.id_fmt_cluster = Onto.get_id_format('site_cluster')['default_format']

    # ───── STEP 7.5a: site_cluster + 멤버십 산출 ─────
    def detect_site_clusters(self) -> List[Tuple[str, List[str]]]:
        """그래프의 vt_site 중 html_src/html_fingerprint를 가진 노드를 군집화.

        Returns: [(cluster_id, [member_url_norm, ...]), ...]
        """
        with self.conn.cursor() as cur:
            cur.execute(f"SET graph_path = {self.graph};")
            # HTML 지문 보유 사이트만 (html_src는 stg에서 적재 시 보존되어야 함)
            cur.execute("""
                MATCH (s:vt_site)
                WHERE s.html_src IS NOT NULL AND s.is_malicious = true
                RETURN s.url_addr, s.html_src
            """)
            rows = cur.fetchall()

        if not rows:
            logger.warning("[site_cluster] html_src를 가진 vt_site가 없음 — STEP 7.5a 건너뜀")
            return []

        # SimHash 계산
        fingerprints = {}
        for url_norm, html in rows:
            url_clean = str(url_norm).strip('"')
            html_clean = str(html).strip('"')
            fingerprints[url_clean] = simhash64(_tokenize_html(html_clean))

        # Pairwise Hamming distance + Union-Find 군집화
        uf = UnionFind()
        urls = list(fingerprints.keys())
        for i in range(len(urls)):
            uf.find(urls[i])  # 단일 자기 그룹 초기화
            for j in range(i + 1, len(urls)):
                if hamming(fingerprints[urls[i]], fingerprints[urls[j]]) <= self.HAMMING_THRESHOLD:
                    uf.union(urls[i], urls[j])

        # cluster_id 부여 + min size 필터
        clusters = []
        for idx, members in enumerate(uf.clusters(), 1):
            if len(members) < self.MIN_CLUSTER_SIZE:
                continue
            cluster_id = f"osint-sc-{idx:04d}"
            clusters.append((cluster_id, members))

        logger.info(f"[site_cluster] 후보 {len(rows)}개 사이트 → {len(clusters)}개 군집 (min={self.MIN_CLUSTER_SIZE})")
        return clusters

    def create_site_clusters(self, clusters: List[Tuple[str, List[str]]]) -> int:
        """STEP 7.5a + 8.5a: site_cluster 노드 + belongs_to_campaign 엣지 생성."""
        created_nodes = 0
        created_edges = 0
        with self.conn.cursor() as cur:
            cur.execute(f"SET graph_path = {self.graph};")
            for cluster_id, members in clusters:
                # 노드 생성 (id_format=plain, source_domain=osint 메타 포함)
                cur.execute(f"""
                    MERGE (c:site_cluster {{cluster_id: '{cluster_id}'}})
                    SET c.cluster_method = 'simhash_union_find',
                        c.id_format = '{self.id_fmt_cluster}',
                        c.source_domain = 'osint',
                        c.site_cnt = {len(members)},
                        c.detected_by = 'osint_v37_postprocess',
                        c.rec_created = toString(now())
                """)
                created_nodes += 1

                # 엣지: vt_site → site_cluster
                for url in members:
                    url_esc = url.replace("'", "\\'")
                    try:
                        cur.execute(f"""
                            MATCH (s:vt_site {{url_addr: '{url_esc}'}}),
                                  (c:site_cluster {{cluster_id: '{cluster_id}'}})
                            MERGE (s)-[r:belongs_to_campaign]->(c)
                            SET r.detected_at = toString(now()),
                                r.source_id = 'osint_v37_postprocess'
                        """)
                        created_edges += 1
                    except Exception as e:
                        logger.warning(f"  엣지 생성 실패 {url}: {e}")
        self.conn.commit()
        logger.info(f"[site_cluster] 노드 {created_nodes} + belongs_to_campaign 엣지 {created_edges} 생성")
        return created_nodes

    # ───── STEP 8.6: vt_id.is_anonymous 마킹 ─────
    def mark_anonymous_ids(self) -> int:
        """OSINT의 vt_id 중 작성자명이 비식별/마스킹된 경우 is_anonymous=true 부여."""
        with self.conn.cursor() as cur:
            cur.execute(f"SET graph_path = {self.graph};")
            try:
                cur.execute("""
                    MATCH (id:vt_id)
                    WHERE id.id_val IS NULL
                       OR id.id_val = ''
                       OR id.id_val LIKE '%****%'
                       OR id.id_val LIKE 'anonymous%'
                       OR id.id_val LIKE 'unknown%'
                    SET id.is_anonymous = true,
                        id.detected_by = 'osint_v37_postprocess'
                    RETURN count(id)
                """)
                row = cur.fetchone()
                count = int(row[0]) if row and row[0] is not None else 0
            except Exception as e:
                logger.warning(f"[is_anonymous] 마킹 실패: {e}")
                count = 0
        self.conn.commit()
        logger.info(f"[is_anonymous] vt_id 마킹: {count}건")
        return count

    # ───── V4.0 메타 보정 (id_format/source_domain/reliability_tier 일괄 적용) ─────
    def apply_v40_meta(self) -> dict:
        """모든 OSINT 노드에 V4.0 표준 메타 보정. 라벨별 누락 메타만 채움.

        - id_format:       Onto.NODE_ID_STANDARD[label]['default_format']
        - source_domain:   'osint'
        - reliability_tier:4
        """
        tier_map = {'osint': 4}
        sd = 'osint'
        default_tier = tier_map[sd]
        out = {}

        with self.conn.cursor() as cur:
            cur.execute(f"SET graph_path = {self.graph};")
            for label in Onto.DOMAIN_USAGE.keys():
                if not Onto.is_applicable(label, sd):
                    continue
                id_fmt_meta = Onto.get_id_format(label)
                default_fmt = id_fmt_meta.get('default_format', 'plain')
                try:
                    cur.execute(f"""
                        MATCH (n:{label})
                        WHERE n.id_format IS NULL OR n.source_domain IS NULL OR n.reliability_tier IS NULL
                        SET n.id_format        = COALESCE(n.id_format, '{default_fmt}'),
                            n.source_domain    = COALESCE(n.source_domain, '{sd}'),
                            n.reliability_tier = COALESCE(n.reliability_tier, {default_tier})
                        RETURN count(n)
                    """)
                    row = cur.fetchone()
                    cnt = int(row[0]) if row and row[0] is not None else 0
                    if cnt > 0:
                        out[label] = cnt
                except Exception as e:
                    logger.warning(f"  [V4.0 메타] {label} 보정 실패: {e}")
                    self.conn.rollback()
                    cur.execute(f"SET graph_path = {self.graph};")
        self.conn.commit()
        total = sum(out.values())
        logger.info(f"[V4.0 메타] OSINT 노드 보정 완료: 총 {total}개 ({len(out)}개 라벨)")
        return out

    # ───── 통합 실행 ─────
    def run_all(self) -> dict:
        out = {"site_clusters": 0, "anonymous_ids": 0, "v40_meta_applied": {}}
        clusters = self.detect_site_clusters()
        if clusters:
            out["site_clusters"] = self.create_site_clusters(clusters)
        out["anonymous_ids"] = self.mark_anonymous_ids()
        # V4.0 표준 메타 일괄 보정
        out["v40_meta_applied"] = self.apply_v40_meta()
        return out


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default="osint_ontology")
    parser.add_argument("--hamming", type=int, default=3, help="SimHash 군집 임계값")
    parser.add_argument("--min-cluster", type=int, default=2, help="군집 최소 크기")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    conn.autocommit = False

    try:
        proc = OsintV37Postprocess(conn, graph_name=args.graph)
        proc.HAMMING_THRESHOLD = args.hamming
        proc.MIN_CLUSTER_SIZE = args.min_cluster
        result = proc.run_all()
        print(f"\n✅ OSINT V3.7 후처리 완료: {result}")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ 실패: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
