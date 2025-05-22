import xml.etree.ElementTree as ET
from collections import defaultdict
import heapq
import json

def parse_net_and_connections(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    lengths = {}
    for edge in root.findall('.//edge'):
        eid = edge.get('id')
        if edge.get('length') is not None:
            lengths[eid] = float(edge.get('length'))
        else:
            lengths[eid] = sum(float(l.get('length', 0.0)) for l in edge.findall('lane'))
    adj = defaultdict(list)
    for conn in root.findall('.//connection'):
        frm = conn.get('from')
        to = conn.get('to')
        if frm and to:
            adj[frm].append((to, lengths.get(to, 1.0)))
    return adj

def parse_parking_areas(add_file):
    tree = ET.parse(add_file)
    root = tree.getroot()
    edges = set()
    edge2pa = defaultdict(list)
    for pa in root.findall('.//parkingArea'):
        lane = pa.get('lane')
        edge = lane.rsplit('_', 1)[0]
        pa_id = pa.get('id')
        edges.add(edge)
        edge2pa[edge].append(pa_id)
    return sorted(edges), edge2pa

def dijkstra(adj, start, target):
    pq = [(0.0, start, [start])]
    visited = set()
    while pq:
        dist, node, path = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            return path
        for neigh, w in adj.get(node, []):
            if neigh not in visited:
                heapq.heappush(pq, (dist + w, neigh, path + [neigh]))
    return None

if __name__ == '__main__':
    NET_FILE            = 'parking.net.xml'
    ADD_FILE            = 'parking.add.xml'
    START_EDGE          = 'E0'
    DESIGNATED_END_EDGE = 'E14'

    adj = parse_net_and_connections(NET_FILE)
    parking_edges, edge2pa = parse_parking_areas(ADD_FILE)

    result = {}

    for park_edge in parking_edges:
        p1 = dijkstra(adj, START_EDGE, park_edge)
        p2 = dijkstra(adj, park_edge, DESIGNATED_END_EDGE)

        if p1 and p2:
            full_path = p1 + p2[1:]
            via = " ".join(full_path)
            for pa_id in edge2pa[park_edge]:
                key = f"{park_edge}_{pa_id}"
                result[key] = {
                    "via": via,
                    "parking": pa_id
                }

    with open('parking_full_routes_test2.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
