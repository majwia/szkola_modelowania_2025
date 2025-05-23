import sys
import os
import numpy as np
import json
import xml.etree.ElementTree as ET
import re
import random
import traci
import csv

NET_FILE = 'parking.net.xml'
routes_file = 'parking_full_routes_test2.json'

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

# PARKING -> LISTA KRAWEDZIE KTORE DO NIEGO PROWADZA
parking_area_to_edges = {}
for edge_id, data in parking_data.items():
    pa = data['parking']
    parking_area_to_edges.setdefault(pa, []).append(edge_id)


# DLUGOSC WSZYSTKICH KRAWEDZI
def get_edge_lengths(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    lengths = {}
    for edge in root.findall('.//edge'):
        eid = edge.get('id')
        length_attr = edge.get('length')
        lengths[eid] = float(length_attr) if length_attr else sum(
            float(l.get('length', 0.0)) for l in edge.findall('lane')
        )
    return lengths

lengths = get_edge_lengths(NET_FILE)

# IM WYZSZY NUMER KRAWEDZI TYM MNIEJSZA WAGA
def get_exp_weights(keys, lambd=0.1):
    values = np.array([int(re.search(r'E(\d+)', k).group(1)) for k in keys])
    weights = np.exp(-lambd * values)
    return weights / weights.sum()


def generate_random_routes(seed = None):
    if seed is not None:
        np.random.seed(seed)
    # ILOSC SAMOCHODOW W SYMULACJI
    max_slots = sum(parking_capacities.values())
    sim_n = int(max_slots * 0.75)

    # AKTUALNA ILOSC JUZ PRZYPISANYCH SAMOCHODOW DO PARKINGU
    assignments = {pa: 0 for pa in parking_capacities}
    vehicles = []
    arrivals = []

    i = 0
    while len(vehicles) < sim_n:
        
        # PARKINGI Z WOLNYMI MIEJSCAMI
        available_pas = [pa for pa in parking_capacities if assignments[pa] < parking_capacities[pa]]
        if not available_pas:
            break
        
        # LOSOWANIE PARKINGU
        pa = random.choice(available_pas)
        edges = parking_area_to_edges[pa]
        weights = get_exp_weights(edges, lambd=0.1)
        edge_id = np.random.choice(edges, p=weights)

        # VIA I PARKING ID
        entry = parking_data[edge_id]
        # VIA
        via_to_park = entry['via'].split()
        # LOSOWY PRZYJAZD
        depart = abs(np.random.normal(20, 10))
        travel_time = sum(lengths.get(e, 0) for e in via_to_park) / 2.89
        # DOJAZD NA MIEJSCA
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

    # KIEDY OSTATNI WJEDZIE NA PARKING
    max_arrival = max(arrivals)
    base_depart = max_arrival + 20.0

    # LISTA ID KRAWEDZI
    edge_nums = np.array([int(re.search(r'E(\d+)', v['edge_id']).group(1)) for v in vehicles])
    sorted_idx = np.argsort(-edge_nums)  
    exp_gaps = np.random.exponential(scale=2.0, size=len(vehicles))
    sorted_departures = base_depart + np.cumsum(exp_gaps)

    veh_output = []
    for i, j in enumerate(sorted_idx):
        v = vehicles[j]
        wait = sorted_departures[i] - v['arrival'] #CZAS POSTOJU NA PARKINGU
        veh_output.append({
            'id': v['id'],
            'depart': v['depart'],
            'via': v['via'],
            'parking': v['parking'],
            'duration': wait
        })

    veh_output.sort(key=lambda v: v['depart']) # POSORTOWANE WEDŁUG DEPART

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

SUMO_BINARY = "sumo"
SUMO_CFG = "parking.sumocfg"
STEP_LENGTH = "0.05"
DELAY = "1"
LATERAL_RES = "0"
N_RUNS = 100
OUT_DIR = "nook1"
os.makedirs(OUT_DIR, exist_ok=True)

def run_simulation(run_id):
    generate_random_routes(seed=run_id)
    xml_out = os.path.join(OUT_DIR, f"tripinfo_run{run_id:03d}.xml")
    sumo_cmd = [
        SUMO_BINARY, "-c", SUMO_CFG, "--start", "--quit-on-end",
        "--step-length", STEP_LENGTH, "--delay", DELAY,
        "--lateral-resolution", LATERAL_RES, "--tripinfo-output", xml_out
    ]
    traci.start(sumo_cmd)

    while traci.simulation.getTime() < 2000:
        traci.simulationStep()
    traci.close()

    tree = ET.parse(xml_out)
    root = tree.getroot()

    def avg(lst): return sum(lst) / len(lst) if lst else 0

    after_parking_times = []
    first_depart_after_parking = float('inf')
    last_arrival = 0
    losses = []

    for ti in root.findall("tripinfo"):
        depart = float(ti.attrib["depart"])
        arrival = float(ti.attrib["arrival"])
        stop_time = float(ti.attrib["stopTime"])
        time_loss = float(ti.attrib["timeLoss"])

        # CZAS WYJAZDU Z PARKINGU
        depart_after = depart + stop_time
        # CZAS POTRZEBNY NA WYJECHANIE PO OPUSZCZENIU MIEJSCA PARKINGOWEGO
        after_parking_times.append(arrival - depart_after)
        # PIERWSZY ODJAZ Z PARKINGU
        first_depart_after_parking = min(first_depart_after_parking, depart_after)
        # KONIEC SYMULKI
        last_arrival = max(last_arrival, arrival)
        # POSTOJE I INNE PRZESZKODY
        losses.append(time_loss)

    return {
        "run_id": run_id,
        "num_veh": len(after_parking_times),
        "avg_travel_time": avg(after_parking_times),
        "total_exit_time": last_arrival - first_depart_after_parking,
        "avg_time_loss": avg(losses)
    }

if __name__ == "__main__":
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    else:
        sys.exit("Brak zmiennej SUMO_HOME")

    all_runs = [run_simulation(i) for i in range(1, N_RUNS + 1)]
    keys = all_runs[0].keys()
    with open(os.path.join(OUT_DIR, "summary.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_runs)
