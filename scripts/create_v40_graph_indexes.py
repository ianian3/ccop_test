"""V4.0 AgensGraph 성능 인덱스 생성 (Sprint 1)
============================================================
25 라벨의 keyProp 에 PROPERTY INDEX 생성 → 점 조회 10~100배 가속.
키 정의 소스: KICSCrimeDomainOntology.NODE_ID_STANDARD (canonical_field)

실행:
    python3 scripts/create_v40_graph_indexes.py [--graph tccop_v40_demo]

옵션:
    --graph <name>  : 대상 그래프 (기본 tccop_v40_demo)
    --dry-run       : 실제 생성 없이 명령만 출력
    --all-graphs    : tccop_v40_demo + tccop_graph_v6 모두
"""
import argparse, sys, logging
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')

from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Ont

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('v40_index')

_app = create_app(); _app.app_context().push()


def create_indexes(graph_name: str, dry_run: bool = False):
    conn, cur = RdbToGraphService.get_db_connection()
    if not conn:
        log.error("DB 연결 실패"); return False

    try:
        safe_set_graph_path(cur, graph_name)
        log.info(f"graph_path = '{graph_name}'")
        created, skipped, failed = 0, 0, 0

        for label, meta in Ont.NODE_ID_STANDARD.items():
            field = meta.get('canonical_field', '')
            # 복합키 (vt_id 등) 처리: '(platform, id_val)' → 첫 컬럼만
            if field.startswith('('):
                field = field.strip('()').split(',')[0].strip()
            if not field or '/' in field:
                continue

            idx_name = f"ix_{label}_{field}"
            stmt = f'CREATE PROPERTY INDEX IF NOT EXISTS {idx_name} ON {label} ({field})'

            if dry_run:
                print(f"  [DRY] {stmt}")
                continue

            try:
                cur.execute(stmt)
                conn.commit()
                log.info(f"  ✅ {idx_name}  ({label}.{field})")
                created += 1
            except Exception as e:
                conn.rollback()
                safe_set_graph_path(cur, graph_name)
                # 이미 존재 / 라벨 없음 등은 정상
                msg = str(e).split('\n')[0][:80]
                if 'already exists' in msg.lower():
                    log.info(f"  ⏭  {idx_name} (already exists)")
                    skipped += 1
                elif 'does not exist' in msg.lower() or 'unknown' in msg.lower():
                    log.warning(f"  ⚠️  {idx_name} (label 없음: {label})")
                    skipped += 1
                else:
                    log.error(f"  ❌ {idx_name} — {msg}")
                    failed += 1

        log.info("=" * 60)
        log.info(f"  graph '{graph_name}': 생성 {created} / 스킵 {skipped} / 실패 {failed}")
        return failed == 0
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph', default='tccop_v40_demo')
    parser.add_argument('--all-graphs', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    graphs = ['tccop_v40_demo', 'tccop_graph_v6'] if args.all_graphs else [args.graph]
    log.info(f"대상 그래프: {graphs} (dry_run={args.dry_run})")

    for g in graphs:
        log.info("=" * 60)
        log.info(f"▶ {g}")
        log.info("=" * 60)
        create_indexes(g, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
