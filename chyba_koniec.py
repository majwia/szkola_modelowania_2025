import sys
import os
import numpy as np
import json
import xml.etree.ElementTree as ET
import re
import random
import traci
import csv

# ---------- Konfiguracja tras i parkowania ----------
NET_FILE = 'mapa22.net.xml'
routes_file = 'parking_full_routes_mapa22.json'

with open(routes_file, 'r', encoding='utf-8') as f:
    parking_data = json.load(f)

parking_capacities = {
    "pa_1": 24, "pa_0": 7, "pa_2": 24, "pa_3": 24, "pa_4": 40,
    "pa_5": 24, "pa_6": 24, "pa_7": 10, "pa_8": 13, "pa_9": 11,
    "pa_10": 12, "pa_11": 11, "pa_12": 7
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
        lengths[eid] = float(length_attr) if length_attr else sum(
            float(l.get('length', 0.0)) for l in edge.findall('lane')
        )
    return lengths

lengths = get_edge_lengths(NET_FILE)


def get_exp_weights(keys, lambd=0.1):
    # Im mniejsza krawędź E, tym wyższe prawdopodobieństwo (ujemne lambda)
    values = np.array([int(re.search(r'E(\d+)', k).group(1)) for k in keys])
    weights = np.exp(-lambd * values)
    return weights / weights.sum()


def generate_random_routes(seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    max_slots = sum(parking_capacities.values())
    # sim_n = np.random.randint(int(0.7 * max_slots), max_slots + 1)
    sim_n = int(max_slots*0.5)
    
    assignments = {pa: 0 for pa in parking_capacities}
    vehicles = []
    arrivals = []
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

    # Sortujemy pojazdy tak, że mniejsze numery krawędzi wyjeżdżają pierwsze
    edge_nums = np.array([int(re.search(r'E(\d+)', v['edge_id']).group(1)) for v in vehicles])
    sorted_idx = np.argsort(edge_nums)
    
    # Możesz też użyć skalowanej rozrzutności czasów:
    # scales = np.linspace(1.0, 3.0, len(vehicles))
    # # Stosunkowo krótsze przerwy dla pojazdów z mniejszymi numerami krawędzi
    edge_nums_sorted = edge_nums[sorted_idx]
    scales = 2.0 + 0.05 * edge_nums_sorted
    exp_gaps = np.random.exponential(scale=scales)

    veh_output = []
    for idx, j in enumerate(sorted_idx):
        v = vehicles[j]
        wait = np.random.uniform(500, 700)
        veh_output.append({
            'id':       v['id'],
            'depart':   v['depart'],
            'via':      v['via'],
            'parking':  v['parking'],
            'duration': wait
        })

    veh_output.sort(key=lambda v: v['depart'])
    exitRoute = "E19"

    with open('mapa22.rou.xml', 'w', encoding='utf-8') as routes:
        routes.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        routes.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ' \
                     'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        routes.write(f'  <route id="exitRoute" edges="{exitRoute}"/>\n')
        for v in veh_output:
            routes.write(f'  <vehicle id="{v["id"]}" depart="{v["depart"]:.2f}">\n')
            routes.write(f'    <route edges="{v["via"]}"/>\n')
            routes.write(f'    <stop parkingArea="{v["parking"]}" duration="{v["duration"]:.2f}"/>\n')
            routes.write('  </vehicle>\n')
        routes.write('</routes>\n')

# ---------- Konfiguracja symulacji ----------
SUMO_BINARY = "sumo"
SUMO_CFG = "mapa22.sumocfg"
STEP_LENGTH = "0.05"
DELAY = "1"
LATERAL_RES = "0"
N_RUNS = 200
OUT_DIR = "sim_results_map1_50"
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

    # Parsuj wyniki
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

        # Nowe metryki: czas po wyjeździe z parkingu
        depart_after = depart + stop_time
        after_parking_times.append(arrival - depart_after)
        first_depart_after_parking = min(first_depart_after_parking, depart_after)
        last_arrival = max(last_arrival, arrival)
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
    print("Wszystkie symulacje zakończone. Wyniki w sim_results/summary.csv")
