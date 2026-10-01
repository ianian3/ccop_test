#!/usr/bin/env python3
"""V4.9 추출조건판(SKAI) 엑셀 생성 — 정본 V4.9 엑셀 + SKAI 9/17판 추출 시트 4종(V4.9 표기로 정합).

정본(handoff/ontology_v4.9/spec/...xlsx)을 scripts/build_ontology_excel.py 로 재생성한 뒤 실행한다.
입력: ~/Downloads/CCOP_Ontology_V4.8_노드엣지속성정보_추출조건_SKAI_20260917.xlsx (저장소 밖 원본)
출력: ~/Downloads/CCOP_Ontology_V4.9_노드엣지속성정보_추출조건_SKAI_20261001.xlsx
"""
import openpyxl, copy, os
D=os.path.expanduser('~/Downloads/')
src=openpyxl.load_workbook(D+'CCOP_Ontology_V4.8_노드엣지속성정보_추출조건_SKAI_20260917.xlsx')
wb=openpyxl.load_workbook('handoff/ontology_v4.9/spec/CCOP_Ontology_V4.9_node_edge_attrs.xlsx')

def cp_style(dst, s):
    dst.font=copy.copy(s.font); dst.fill=copy.copy(s.fill); dst.border=copy.copy(s.border)
    dst.alignment=copy.copy(s.alignment); dst.number_format=s.number_format; dst.protection=copy.copy(s.protection)

def clone(ws_src, title, index=None):
    ws=wb.create_sheet(title, index)
    for row in ws_src.iter_rows():
        for c in row:
            n=ws.cell(c.row, c.column, c.value)
            if c.has_style: cp_style(n, c)
    for k,d in ws_src.column_dimensions.items(): ws.column_dimensions[k].width=d.width
    for k,d in ws_src.row_dimensions.items():
        if d.height: ws.row_dimensions[k].height=d.height
    ws.freeze_panes=ws_src.freeze_panes
    for m in ws_src.merged_cells.ranges: ws.merge_cells(str(m))
    return ws

nodes=clone(src['추출가능_노드속성'],'추출가능_노드속성',0)
edges=clone(src['추출가능_엣지속성'],'추출가능_엣지속성',1)
clone(src['쿼리연산자'],'쿼리연산자',2)
clone(src['SKAI_추가근거'],'SKAI_추가근거')

rows={(nodes.cell(r,1).value, nodes.cell(r,2).value): r for r in range(2, nodes.max_row+1)}
nodes.cell(rows[('vt_id','id_val')],4).value='식별자 값(예: gildong99 · 이메일은 소문자 정규화 주소)'
nodes.cell(rows[('vt_id','platform')],4).value='KakaoTalk|Telegram|Instagram|Naver…|email (V4.9: 이메일은 platform=email)'
r=rows[('vt_email','provider')]; nodes.cell(r,1).value='vt_id'; nodes.cell(r,4).value='이메일 제공사 Gmail|Naver|Daum|Unknown (platform=email 일 때)'
nodes.delete_rows(rows[('vt_email','email_addr')])

er={edges.cell(r,1).value: r for r in range(2, edges.max_row+1)}
r=er['match_score']; edges.cell(r,1).value='confidence'; edges.cell(r,3).value='엔티티 매칭 신뢰도 0.0~1.0 (V4.9: 구 match_score)'
edges.cell(er['first_seen / last_seen'],4).value='used_in_device'
edges.cell(er['link_basis'],4).value='linked_to'
for a,txt in (('first_dlng_dt','이체 쌍의 첫 거래일시 (V4.9: 원천 이체 쌍 집계)'),('last_dlng_dt','이체 쌍의 마지막 거래일시 (V4.9: 원천 이체 쌍 집계)'),
              ('txn_count','이체 쌍의 거래 건수 (V4.9: 원천 이체 쌍 집계)'),('total_amount','이체 쌍의 거래 총액(원) (V4.9: 원천 이체 쌍 집계)')):
    edges.cell(er[a],3).value=txt
for a in ('first_dt','last_dt'): edges.cell(er[a],4).value='contacted, located_at'
edges.cell(er['usage_count'],3).value='IP 사용 횟수 (V4.9: (주체, IP) 쌍 집계)'
last=edges.max_row
for vals in (['evt_count','int','V4.9. 위치 관측 건수 (시각 있는 원천 행 수)','located_at','수치형'],
             ['access_type','str','V4.9. 접속 유형 — 여러 값은 | 로 결합','used_ip','범주형'],
             ['basis','str',"V4.9. 사이트→IP 연결 근거 — 'dns'(DNS 관측) · 'origin'(원본 서버 확인)",'resolves_to','범주형'],
             ['review_status','str','V4.9. 동일인 검토 상태 pending|confirmed|rejected','same_as','범주형']):
    last+=1
    for j,x in enumerate(vals):
        c=edges.cell(last,j+1,x); cp_style(c, edges.cell(last-1,j+1))

h=wb['변경이력(V4.3→V4.9)']; hl=h.max_row
vals=['R31','V4.9','추출조건','추출가능_노드속성 · 추출가능_엣지속성 (SKAI 9/17판 이식)',
      'V4.8 표기: vt_email.email_addr·provider, same_as.match_score, linked_id.link_basis, used_ip.first_seen/last_seen, transferred_to "추론경로" 설명',
      'vt_id(platform=email) 로 흡수, confidence, linked_to, used_in_device 만, 원천 쌍 집계 설명. 추가 4행: located_at.evt_count · used_ip.access_type · resolves_to.basis · same_as.review_status',
      '쿼리연산자·SKAI_추가근거 시트는 내용 그대로 이식 (contacted 실데이터 근거는 V4.9 에서도 유효)']
for j,x in enumerate(vals):
    c=h.cell(hl+1,j+1,x); cp_style(c, h.cell(hl,j+1))

out=D+'CCOP_Ontology_V4.9_노드엣지속성정보_추출조건_SKAI_20261001.xlsx'
wb.save(out); print(out)
print([(ws.title, ws.max_row) for ws in openpyxl.load_workbook(out, read_only=True)])
