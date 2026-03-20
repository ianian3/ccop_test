import sys

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Cytoscape styles for new Nodes (vt_transfer, vt_call, vt_loc_evt, vt_vhcl)
old_styles = """
                { selector: 'node[label="vt_id"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#fab1a0', 'label': function (ele) { const p = ele.data('props') || {}; return p.id || p.user_id || 'ID'; } } },
                { selector: 'node[label="vt_event"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#00cec9', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return (p.event_type || 'Event') + '\\n[' + (p.amount || p.duration || '') + ']'; }, 'text-wrap': 'wrap' } },
"""
new_styles = """
                { selector: 'node[label="vt_id"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#fab1a0', 'label': function (ele) { const p = ele.data('props') || {}; return p.id || p.user_id || 'ID'; } } },
                { selector: 'node[label="vt_transfer"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#e84393', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return '이체\\n[' + (p.amount || '') + ']'; }, 'text-wrap': 'wrap' } },
                { selector: 'node[label="vt_call"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#e84393', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return '통화\\n[' + (p.duration || '') + ']'; }, 'text-wrap': 'wrap' } },
                { selector: 'node[label="vt_vhcl"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#fdcb6e', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return p.vhclno || '차량'; }, 'text-wrap': 'wrap' } },
                { selector: 'node[label="vt_loc_evt"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#00cec9', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return '위치이벤트\\n[' + (p.lat ? 'geo' : '') + ']'; }, 'text-wrap': 'wrap' } },
                { selector: 'node[label="vt_event"]', style: { 'background-image': '/static/images/person.png', 'background-fit': 'cover', 'border-color': '#00cec9', 'border-width': 4, 'label': function (ele) { const p = ele.data('props') || {}; return (p.event_type || 'Event') + '\\n[' + (p.amount || p.duration || '') + ']'; }, 'text-wrap': 'wrap' } },
"""
html = html.replace(old_styles, new_styles)

# 2. Update the buttons in the "RDB 테이블 데이터 조회" section
old_buttons = """
                    <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
                        <button onclick="queryRdbTable('rdb_cases')" class="rdb-table-btn"
                            style="background: #6c5ce7; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">📁
                            사건</button>
                        <button onclick="queryRdbTable('rdb_suspects')" class="rdb-table-btn"
                            style="background: #e17055; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">👤
                            피의자</button>
                        <button onclick="queryRdbTable('rdb_accounts')" class="rdb-table-btn"
                            style="background: #00b894; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">💳
                            계좌</button>
                        <button onclick="queryRdbTable('rdb_phones')" class="rdb-table-btn"
                            style="background: #e84393; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">📞
                            전화번호</button>
                        <button onclick="queryRdbTable('rdb_transfers')" class="rdb-table-btn"
                            style="background: #fdcb6e; color:#333; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">💸
                            이체내역</button>
                    </div>
"""
new_buttons = """
                    <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
                        <button onclick="queryRdbTable('TB_INCDNT_MST')" class="rdb-table-btn"
                            style="background: #6c5ce7; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">📁
                            사건(V2)</button>
                        <button onclick="queryRdbTable('TB_PRSN')" class="rdb-table-btn"
                            style="background: #e17055; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">👤
                            인물(V2)</button>
                        <button onclick="queryRdbTable('TB_FIN_BACNT')" class="rdb-table-btn"
                            style="background: #00b894; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">💳
                            계좌(V2)</button>
                        <button onclick="queryRdbTable('TB_FIN_BACNT_DLNG')" class="rdb-table-btn"
                            style="background: #fdcb6e; color:#333; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">💸
                            이체내역(V2)</button>
                        <button onclick="queryRdbTable('TB_TELNO_CALL_DTL')" class="rdb-table-btn"
                            style="background: #e84393; color:white; padding:7px 14px; border:none; border-radius:4px; cursor:pointer; font-size:12px;">📞
                            통화내역(V2)</button>
                    </div>
"""
html = html.replace(old_buttons, new_buttons)

# 3. Update the table select dropdown
old_select = """
                                        <option value="">테이블 선택...</option>
                                        <option value="rdb_suspects">rdb_suspects (인물)</option>
                                        <option value="rdb_accounts">rdb_accounts (계좌)</option>
                                        <option value="rdb_phones">rdb_phones (전화번호)</option>
                                        <option value="rdb_cases">rdb_cases (사건)</option>
"""
new_select = """
                                        <option value="">테이블 선택...</option>
                                        <option value="TB_PRSN">TB_PRSN (인물)</option>
                                        <option value="TB_FIN_BACNT">TB_FIN_BACNT (계좌)</option>
                                        <option value="TB_TELNO_MST">TB_TELNO_MST (전화번호)</option>
                                        <option value="TB_INCDNT_MST">TB_INCDNT_MST (사건)</option>
                                        <option value="TB_FIN_BACNT_DLNG">TB_FIN_BACNT_DLNG (이체)</option>
"""
html = html.replace(old_select, new_select)

# 4. Update JS stats tableNames
old_tab_names = """
                        const tableNames = {
                            'rdb_cases': '사건', 'rdb_suspects': '피의자',
                            'rdb_accounts': '계좌', 'rdb_phones': '전화',
                            'rdb_transfers': '이체', 'rdb_calls': '통화',
                            'rdb_relations': '관계'
                        };
"""
new_tab_names = """
                        const tableNames = {
                            'TB_INCDNT_MST': '사건', 'TB_PRSN': '인물',
                            'TB_FIN_BACNT': '계좌', 'TB_TELNO_MST': '전화',
                            'TB_FIN_BACNT_DLNG': '이체', 'TB_TELNO_CALL_DTL': '통화'
                        };
"""
html = html.replace(old_tab_names, new_tab_names)

# 5. Update graph icon map for info window
old_icons = """
                        const icons = {
                            'rdb_cases': '📁', 'rdb_suspects': '👤',
                            'rdb_accounts': '💳', 'rdb_phones': '📞',
                            'rdb_transfers': '��', 'rdb_calls': '📲',
                            'rdb_relations': '🔗'
                        };
"""
new_icons = """
                        const icons = {
                            'TB_INCDNT_MST': '📁', 'TB_PRSN': '👤',
                            'TB_FIN_BACNT': '💳', 'TB_TELNO_MST': '📞',
                            'TB_FIN_BACNT_DLNG': '💸', 'TB_TELNO_CALL_DTL': '📲'
                        };
"""
html = html.replace(old_icons, new_icons)

with open('app/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
