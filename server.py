from flask import Flask, jsonify, send_from_directory, request
import json
import os

app = Flask(__name__, static_folder='static')

DATA_DIR = 'data'

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Загружаем справочники один раз при старте
zones_list = load_json('zones.json')
ip_lists_meta = load_json('ipaddr_list_random.json')
services_list = load_json('services.json')

# Строим словари: id -> имя
zone_names = {z['id']: z['name'] for z in zones_list}
service_names = {s['id']: s['name'] for s in services_list}
# Словарь ID IP-листов -> имя (из ipaddr_list_random)
ip_list_names = {item['id']: item['name'] for item in ip_lists_meta}

def parse_ips(ips):
    """Преобразовать список IP-объектов правила в читаемый текст."""
    if not ips:
        return 'any'
    parts = []
    for entry in ips:
        typ = entry[0]
        val = entry[1]
        if typ == 'list_id':
            name = ip_list_names.get(val, f'List-{val}')
            parts.append(name)
        elif typ == 'geoip_code':
            parts.append(f'GeoIP:{val}')
        else:
            parts.append(str(val))
    return ', '.join(parts) if parts else 'any'

def parse_services(svc_ids):
    if not svc_ids:
        return 'any'
    return ', '.join([service_names.get(sid, f'Svc-{sid}') for sid in svc_ids])

def parse_apps(apps):
    if not apps:
        return 'any'
    parts = []
    for app in apps:
        if app[0] == 'app':
            parts.append(f'App-{app[1]}')
        elif app[0] == 'ro_group':
            parts.append(f'AppGroup-{app[1]}')
        else:
            parts.append(str(app))
    return ', '.join(parts) if parts else 'any'

def build_graph_for_rules(rules):
    elements = []
    # Узлы – зоны, которые упоминаются в правилах
    zones_in_use = set()
    for rule in rules:
        for zid in rule.get('src_zones', []):
            zones_in_use.add(zid)
        for zid in rule.get('dst_zones', []):
            zones_in_use.add(zid)

    # Создаём составные узлы для зон
    for zid in zones_in_use:
        name = zone_names.get(zid, f'Zone-{zid}')
        elements.append({
            'data': {
                'id': f'zone-{zid}',
                'label': name,
                'type': 'zone'
            }
        })

    # Правила как рёбра между зонами (агрегируем по паре зон и действию)
    edge_groups = {}
    for rule in rules:
        if not rule.get('enabled', False):
            continue
        action = rule.get('action', 'accept')
        src_zones = rule.get('src_zones', [])
        dst_zones = rule.get('dst_zones', [])
        if not src_zones or not dst_zones:
            # Если хотя бы одна зона отсутствует, пропускаем для простоты
            continue

        for src in src_zones:
            for dst in dst_zones:
                key = (src, dst, action)
                if key not in edge_groups:
                    edge_groups[key] = {
                        'count': 0,
                        'sources': set(),
                        'destinations': set(),
                        'services': set(),
                        'apps': set(),
                        'rule_ids': set()
                    }
                edge_groups[key]['count'] += 1
                edge_groups[key]['sources'].add(parse_ips(rule.get('src_ips', [])))
                edge_groups[key]['destinations'].add(parse_ips(rule.get('dst_ips', [])))
                edge_groups[key]['services'].add(parse_services(rule.get('services', [])))
                edge_groups[key]['apps'].add(parse_apps(rule.get('apps', [])))
                edge_groups[key]['rule_ids'].add(rule.get('id'))

    for (src, dst, action), info in edge_groups.items():
        label = f'{info["count"]} rule(s)'
        title = f'Sources: {"; ".join(info["sources"])}\nDestinations: {"; ".join(info["destinations"])}\nServices: {"; ".join(info["services"])}\nApps: {"; ".join(info["apps"])}'
        elements.append({
            'data': {
                'id': f'edge-{src}-{dst}-{action}',
                'source': f'zone-{src}',
                'target': f'zone-{dst}',
                'action': action,
                'label': label,
                'title': title,
                'count': info['count'],
                'rules': list(info['rule_ids'])
            }
        })

    return elements

@app.route('/api/graph')
def graph():
    source = request.args.get('source', 'fw')  # fw или web
    action_filter = request.args.get('action', 'all')
    status_filter = request.args.get('status', 'all')

    if source == 'web':
        rules = load_json('web_rules_random.json')
    else:
        rules = load_json('fw_rules_random_result.json')

    # Фильтрация по действию
    if action_filter != 'all':
        rules = [r for r in rules if r.get('action') == action_filter]
    # Фильтрация по статусу
    if status_filter == 'enabled':
        rules = [r for r in rules if r.get('enabled', False)]
    elif status_filter == 'disabled':
        rules = [r for r in rules if not r.get('enabled', False)]

    elements = build_graph_for_rules(rules)
    return jsonify({'elements': elements, 'total': len(rules)})

@app.route('/api/rules')
def rules_list():
    """Возвращает список правил с деталями для таблицы."""
    source = request.args.get('source', 'fw')
    action_filter = request.args.get('action', 'all')
    status_filter = request.args.get('status', 'all')

    if source == 'web':
        rules = load_json('web_rules_random.json')
    else:
        rules = load_json('fw_rules_random_result.json')

    if action_filter != 'all':
        rules = [r for r in rules if r.get('action') == action_filter]
    if status_filter == 'enabled':
        rules = [r for r in rules if r.get('enabled', False)]
    elif status_filter == 'disabled':
        rules = [r for r in rules if not r.get('enabled', False)]

    result = []
    for rule in rules:
        result.append({
            'id': rule.get('id'),
            'name': rule.get('name', ''),
            'position': rule.get('position', ''),
            'action': rule.get('action', ''),
            'enabled': rule.get('enabled', False),
            'src_zones': [zone_names.get(z, str(z)) for z in rule.get('src_zones', [])],
            'dst_zones': [zone_names.get(z, str(z)) for z in rule.get('dst_zones', [])],
            'src_ips': parse_ips(rule.get('src_ips', [])),
            'dst_ips': parse_ips(rule.get('dst_ips', [])),
            'services': parse_services(rule.get('services', [])),
            'apps': parse_apps(rule.get('apps', []))
        })
    return jsonify({'rules': result})

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
