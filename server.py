from flask import Flask, jsonify, send_from_directory
import os

app = Flask(__name__, static_folder='static')

def build_graph():
    nodes = [
        {'data': {'id': 'zone-internet', 'label': 'Internet', 'type': 'zone'}},
        {'data': {'id': 'zone-dmz',     'label': 'DMZ',     'type': 'zone'}},
        {'data': {'id': 'zone-lan',     'label': 'LAN',     'type': 'zone'}},

        {'data': {'id': 'net-internet-any', 'label': '0.0.0.0/0', 'parent': 'zone-internet'}},
        {'data': {'id': 'srv-dmz-web', 'label': 'HTTP/HTTPS', 'parent': 'zone-dmz'}},
        {'data': {'id': 'srv-dmz-ssh', 'label': 'SSH', 'parent': 'zone-dmz'}},
        {'data': {'id': 'net-lan-local', 'label': '192.168.1.0/24', 'parent': 'zone-lan'}},
        {'data': {'id': 'net-lan-admins', 'label': 'Admins', 'parent': 'zone-lan'}},
    ]

    edges = [
        {'data': {'id': 'rule1', 'source': 'net-internet-any', 'target': 'srv-dmz-web',
                  'action': 'allow', 'service': 'HTTP/HTTPS', 'label': 'Allow Web'}},
        {'data': {'id': 'rule2', 'source': 'net-lan-local', 'target': 'net-internet-any',
                  'action': 'allow', 'service': 'HTTP/HTTPS', 'label': 'Allow Web out'}},
        {'data': {'id': 'rule3', 'source': 'net-lan-admins', 'target': 'srv-dmz-ssh',
                  'action': 'allow', 'service': 'SSH', 'label': 'Admin SSH'}},
        {'data': {'id': 'rule4', 'source': 'net-internet-any', 'target': 'net-lan-local',
                  'action': 'deny',  'service': 'any', 'label': 'Deny all'}},
    ]
    return nodes + edges

@app.route('/api/graph')
def graph():
    return jsonify({'elements': build_graph()})

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
