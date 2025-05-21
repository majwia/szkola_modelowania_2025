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

# SCIEZKI DO ROZKLADU PARKINGU I TRAS
NET_FILE      = 'test2.net.xml'
routes_file   = 'parking_full_routes_test2.json'

# WCZYTANIE TRAS I MIEJSC PARKINGOWYCH PO DRODZE
with open(routes_file, 'r', encoding='utf-8') as f:
    parking_data = json.load(f)

# RECZNIE USTAWIC ILE KAZDY PARKING MA MIEJSCA
parking_capacities = {
    "pa_1": 16,
    "pa_0": 15,
    "pa_2": 13,
    "pa_3": 9,
    "pa_4": 11
}

# LISTA KRAWEDZI PO KTORYCH MOZNA WJECHAC NA PARKING
parking_area_to_edges = {}
for edge_id, data in parking_data.items():
    pa = data['parking']
    if pa not in parking_area_to_edges:
        parking_area_to_edges[pa] = []
    parking_area_to_edges[pa].append(edge_id)

# DO SZACOWANIA CZASU DOJAZDU DO MIEJSCA PARKINGOWEGO
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
            lengths[eid] = sum(float(l.get('length',0.0)) for l in edge.findall('lane'))
    return lengths

lengths = get_edge_lengths(NET_FILE)

# PREFERENCYJNE MIEJSCA
def get_exp_weights(keys, lambd=0.1):
    values = np.array([int(re.search(r'E(\d+)', k).group(1)) for k in keys])
    weights = np.exp(lambd * values)
    return weights / weights.sum()

def generate_random_routes():
    max_slots = sum(parking_capacities.values())
    # ILOSC SAMOCHODOW W SYMULACJI OD 70% DO 100
    sim_n = np.random.randint(int(0.7 * max_slots), max_slots + 1)

    assignments = {pa: 0 for pa in parking_capacities}
    vehicles = []
    arrivals = []
    np.random.seed(69)

    i = 0
    # LOSOWANIE PARKINGOW
    while len(vehicles) < sim_n:
        available_pas = [pa for pa in parking_capacities if assignments[pa] < parking_capacities[pa]]
        if not available_pas:
            break

        pa = random.choice(available_pas)
        edges = parking_area_to_edges[pa]
        weights = get_exp_weights(edges, lambd=0.1)
        edge = np.random.choice(edges, p=weights)

        entry = parking_data[edge]
        full_via = entry['via'].split()
        if edge not in full_via:
            continue
        idx = full_via.index(edge)
        via_to_park = full_via[:idx+1]

        # depart = abs(np.random.normal(scale=600)) # DO LICZENIA CZASOW DLA REALNEJ SYMULACJI
        depart = abs(np.random.normal(20,10)) # DO POKAZU NA PREZENTACJE CZY COS
        travel_time = sum(lengths.get(e, 0) for e in via_to_park) / 13.89
        arrival = depart + travel_time

        vehicles.append({
            'id': f"veh{i}",
            'depart': depart,
            'via': " ".join(via_to_park),
            'parking': pa,
            'arrival': arrival,
            'edge_id': edge
        })
        arrivals.append(arrival)
        assignments[pa] += 1
        i += 1

    # SYNCHRONIZACJA CZASOW ODJAZDU
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
        wait = max(wait, 0.0)
        veh_output.append({
            'id': v['id'],
            'depart': v['depart'],
            'via': v['via'],
            'parking': v['parking'],
            'duration': wait
        })

    # PRZY ZAPISIE DO PLIKU MUSZA BYC POSORTOWANE PO DEPART
    veh_output.sort(key=lambda v: v['depart'])
    exitRoute = "E9"
    
    with open('test2.rou.xml', 'w', encoding='utf-8') as routes:
        print('<?xml version="1.0" encoding="UTF-8"?>', file=routes)
        print('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">', file=routes)
        print(f'  <route id="exitRoute" edges="{exitRoute}"/>', file=routes)

        for v in veh_output:
            print(f'  <vehicle id="{v["id"]}" depart="{v["depart"]}">', file=routes)
            print(f'    <route edges="{v["via"]}"/>', file=routes)
            print(f'    <stop parkingArea="{v["parking"]}" duration="{v["duration"]:.2f}"/>', file=routes)
            print('  </vehicle>', file=routes)

        print('</routes>', file=routes)

if __name__ == '__main__':
    generate_random_routes()