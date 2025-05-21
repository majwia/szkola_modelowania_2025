import sys
import os
import numpy as np
import json

#es
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("niezly parking 'SUMO_HOME'")

routs_file = r'sosna_son.json'

with open(routs_file, 'r') as f:
    # miejsca i droga do wyjazdu
    parking_slots_via = json.load(f)

# wszystkie miejsca parkingowe
parkings = list(parking_slots_via.keys())

def generate_random_routes():
    
    # ilosc samochodow w symulacji
    # sim_n = np.random.choice(np.arange(int(len(parkings)*0.2), len(parkings)))
    # sim_n = 15
    sim_n = 2
    parking_sim_slots = np.random.choice(parkings, sim_n, replace=False)
    # indexy numeryczne, im mniejszy tym blizej wyjscia
    slot_nums = np.array([int(s.lstrip('E')) for s in parking_sim_slots])
    
    c = 2000
    begin_times = np.random.exponential(c / slot_nums) 
    
    order = np.argsort(begin_times)
    sorted_times = begin_times[order] + 10
    sorted_slots = [parking_sim_slots[i] for i in order]
    
    with open(r'testylepsze/plsparking.rou.xml', 'w') as routes:
        print('<?xml version="1.0" encoding="UTF-8"?>', file=routes)
        print('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">', file=routes)        
        # for i, slot in enumerate(sorted_slots):
        #     print(f'     <trip id="t_{i}" depart="{sorted_times[i]:.3f}" from="{slot}" to="W7" via="{parking_slots_via[slot]}"/>', file=routes)
        for i, slot in enumerate(sorted_slots):
            print(f'<vehicle id="veh{i}" depart="{np.random.randint(5,50)}">', file=routes)
            print(f'    <route edges="{parking_slots_via[slot]}"/>', file=routes)
            print(f'    <stop parkingArea="pa_{0}" duration="{max(sorted_times)}"/>', file=routes)
            print(f'</vehicle>', file=routes)
        print('</routes>', file=routes)
    
generate_random_routes()
