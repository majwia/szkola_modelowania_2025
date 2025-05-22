import sys
import os
import numpy as np
import json
import xml.etree.ElementTree as ET
import re
import random

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Brak zmiennej SUMO_HOME")

NET_FILE      = 'parking.net.xml'
routes_file   = 'parking_full_routes_test2.json'

with open(routes_file, 'r', encoding='utf-8') as f:
    parking_data = json.load(f)

parking_capacities = {
    "pa_0": 9, "pa_1": 9, "pa_2": 8, "pa_3": 10, "pa_4": 9,
    "pa_10": 10, "pa_11": 8, "pa_12": 8, "pa_20": 9, "pa_21": 9,
    "pa_22": 8, "pa_23": 6, "pa_24": 5, "pa_29": 6, "pa_30": 9,
    "pa_31": 8, "pa_32": 9, "pa_33": 5, "pa_39": 5, "pa_40": 12,
    "pa_41": 8, "pa_42": 6, "pa_43": 4, "pa_49": 7, "pa_50": 8,
    "pa_51": 4, "pa_52": 8, "pa_53": 8
}

parking_area_to_edges = {}
for edge_id, data in parking_data.items():
    pa = data['parking']
    parking_area_to_edges.setdefault(pa, []).append(edge_id)

def get_edge_lengths(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    lengths = {}
    for edge in root.findall('.//edge'):
        eid = edge.get('id')
        length_attr = edge.get('length')
        if length_attr:
            lengths[eid] = float(length_attr)
        else:
            lengths[eid] = sum(float(l.get('length', 0.0)) for l in edge.findall('lane'))
    return lengths

lengths = get_edge_lengths(NET_FILE)

def get_exp_weights(keys, lambd=0.1):
    values = np.array([int(re.search(r'E(\d+)', k).group(1)) for k in keys])
    weights = np.exp(lambd * values)
    return weights / weights.sum()

def generate_random_routes():
    max_slots = sum(parking_capacities.values())
    sim_n = np.random.randint(int(0.7 * max_slots), max_slots + 1)

    assignments = {pa: 0 for pa in parking_capacities}
    vehicles = []
    arrivals = []
    np.random.seed(69)

    i = 0
    while len(vehicles) < sim_n:
        available_pas = [pa for pa in parking_capacities if assignments[pa] < parking_capacities[pa]]
        if not available_pas:
            break

        pa = random.choice(available_pas)
        edges = parking_area_to_edges[pa]
        weights = get_exp_weights(edges, lambd=0.1)
        edge_id = np.random.choice(edges, p=weights)

        entry = parking_data[edge_id]
        via_to_park = entry['via'].split()
        depart = abs(np.random.normal(20, 10))
        travel_time = sum(lengths.get(e, 0) for e in via_to_park) / 13.89
        arrival = depart + travel_time

        vehicles.append({
            'id': f"veh{i}",
            'depart': depart,
            'via': " ".join(via_to_park),
            'parking': pa,
            'arrival': arrival,
            'edge_id': edge_id
        })
        arrivals.append(arrival)
        assignments[pa] += 1
        i += 1

    max_arrival = max(arrivals)
    base_depart = max_arrival + 20.0

    edge_nums = np.array([int(re.search(r'E(\d+)', v['edge_id']).group(1)) for v in vehicles])
    sorted_idx = np.argsort(-edge_nums)
    exp_gaps = np.random.exponential(scale=2.0, size=len(vehicles))
    sorted_departures = base_depart + np.cumsum(exp_gaps)

    veh_output = []
    for i, j in enumerate(sorted_idx):
        v = vehicles[j]
        wait = sorted_departures[i] - v['arrival']
        wait = np.random.uniform(500, 700)
        veh_output.append({
            'id': v['id'],
            'depart': v['depart'],
            'via': v['via'],
            'parking': v['parking'],
            'duration': wait
        })

    veh_output.sort(key=lambda v: v['depart'])
    exitRoute = "E14"
    
    with open('parking.rou.xml', 'w', encoding='utf-8') as routes:
        print('<?xml version="1.0" encoding="UTF-8"?>', file=routes)
        print('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">', file=routes)
        print(f'  <route id="exitRoute" edges="{exitRoute}"/>', file=routes)

        for v in veh_output:
            print(f'  <vehicle id="{v["id"]}" depart="{v["depart"]:.2f}">', file=routes)
            print(f'    <route edges="{v["via"]}"/>', file=routes)
            print(f'    <stop parkingArea="{v["parking"]}" duration="{v["duration"]:.2f}"/>', file=routes)
            print('  </vehicle>', file=routes)

        print('</routes>', file=routes)

if __name__ == '__main__':
    generate_random_routes()
