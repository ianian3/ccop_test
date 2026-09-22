"""Read-only ontology probes. No database or application initialization."""
import contextlib, io, json, runpy, sys, types, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
def read(p): return runpy.run_path(str(ROOT / p))
O = read('app/middleware/services/ontology_service.py')['KICSCrimeDomainOntology']
H = read('handoff/ontology_v4.8/code/ccop_ontology_v48.py')['KICSCrimeDomainOntology']
result = {'snapshot': '39b78ec', 'counts': {'nodes': len(O.ENTITIES), 'edges': len(O.RELATIONSHIPS), 'active_edges': len(O.active_relationships()), 'layers': len(O.LAYERS)}, 'canonical_not_declared': {}, 'handoff_core_sync': {}, 'abstract_endpoints': []}
for concept, ent in O.ENTITIES.items():
    key = O.NODE_ID_STANDARD[ent['label']]['canonical_field']
    keys = [s.strip() for s in key.strip('()').split(',')]
    missing = set(keys) - set(ent['properties']) - set(ent['attributes'])
    if missing: result['canonical_not_declared'][concept] = {'canonical': key, 'properties': ent['properties'], 'missing': sorted(missing)}
for key in ['ENTITIES', 'NODE_ID_STANDARD', 'EDGE_META_SCHEMA', 'GDB_LABEL_MAP']:
    result['handoff_core_sync'][key] = getattr(O,key) == getattr(H,key)
result['handoff_core_sync']['relation_contracts'] = all({k:v for k,v in r.items() if k not in ('semantic_relation','source_types')} == H.RELATIONSHIPS[n] for n,r in O.RELATIONSHIPS.items())
for name, rel in O.RELATIONSHIPS.items():
    for side in ('domain','range'):
        for token in rel[side].split('|'):
            if token not in O.ENTITIES: result['abstract_endpoints'].append([name,side,token])
with zipfile.ZipFile(ROOT/'handoff/ontology_v4.8.zip') as z:
    n = next(n for n in z.namelist() if n.endswith('ccop_ontology_v48.py'))
    ns = {}; exec(compile(z.read(n),n,'exec'),ns)
    result['zip_case_key'] = ns['KICSCrimeDomainOntology'].NODE_ID_STANDARD['vt_case']
ip = read('app/services/ip_role_temporal.py')
vf,vt = ip['derive_valid_interval']('2026-09-01T10:00:00','2026-09-03T18:00:00')
result['time_probe'] = {'derived': [vf,vt], 'last_observation_in_interval': vf <= '2026-09-03T18:00:00' < vt}
# Inject only an inert database stub, feeding synthetic query results to the actual audit.
class Cursor:
    def execute(self, sql): self.sql = sql
    def fetchall(self):
        if 'label(n)' in self.sql: return [('vt_psn',)]
        return []
    def fetchone(self): return (0 if 'IS NOT NULL' in self.sql else 1,)
class Connection:
    def cursor(self): return Cursor()
    def close(self): pass
stub = types.ModuleType('psycopg2'); stub.connect = lambda **kwargs: Connection()
sys.modules['psycopg2'] = stub
sys.path.insert(0,str(ROOT/'handoff/ontology_v4.8/code'))
audit = read('handoff/ontology_v4.8/code/audit_ontology_v48.py')
sys.argv = ['audit','--graph','synthetic_graph']
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try: audit['main']()
    except SystemExit as exc: result['missing_key_source_exit_code'] = exc.code
result['missing_key_source_output'] = buf.getvalue()
result['linked_id_accepts_account'] = 'vt_bacnt' in {audit['label_of'](t.strip()) for t in O.RELATIONSHIPS['linked_id']['domain'].split('|')}
print(json.dumps(result,ensure_ascii=False,indent=2))
