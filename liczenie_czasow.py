#zajebane

# Step 1: Add modules to provide access to specific libraries and functions
import os  # Module provides functions to handle file paths, directories, environment variables
import sys  # Module provides access to Python-specific system parameters and functions

# Step 2: Establish path to SUMO (SUMO_HOME)
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

# Step 3: Add Traci module to provide access to specific libraries and functions
import traci  # Provides access to SUMO's TraCI API

# Step 4: Define Sumo configuration
Sumo_config = [
    'sumo-gui',
    '-c', r'sciezkadopliku.sumocfg',
    '--step-length', '0.05',
    '--delay', '1000',
    '--lateral-resolution', '0'
]

# Step 5: Open connection between SUMO and Traci
traci.start(Sumo_config)

# Step 6: Define Variables
# Dictionary to store the departure time of each vehicle when they first appear in the simulation
depart_times = {}
# Dictionary to store computed travel times for vehicles after they have arrived
travel_times = {}

# Step 7: Define Functions
def update_vehicle_times(current_time, depart_times, travel_times):
    """
    Updates the departure times for new vehicles and computes travel times for vehicles that have arrived.
    Prints the travel time for each vehicle that has arrived.
    """
    sum = 0
    # Record departure time for vehicles that just entered the simulation
    for veh_id in traci.vehicle.getIDList():
        if veh_id not in depart_times:
            depart_times[veh_id] = current_time

    # Check for vehicles that have arrived in this simulation step
    arrived_vehicles = traci.simulation.getArrivedIDList()
    for veh_id in arrived_vehicles:
        if veh_id in depart_times:
            # Compute travel time as the difference between current simulation time and departure time
            d = current_time - depart_times[veh_id]
            # sum += d
            travel_times[veh_id] = d
            print(f"Vehicle {veh_id} travel time: {travel_times[veh_id]:.2f} seconds")
            # print(f'sum: {d}')

# Step 8: Take simulation steps until simulation time reaches 3600 seconds
while traci.simulation.getTime() < 2000:
    
    traci.simulationStep()  # Move simulation forward 1 step
    current_time = traci.simulation.getTime()
    update_vehicle_times(current_time, depart_times, travel_times)

# After simulation, compute and print the average travel time
if travel_times:
    average_travel_time = sum(travel_times.values()) / len(travel_times)
    print(f"Average travel time of all vehicles: {average_travel_time:.2f} seconds")
else:
    print("No travel time data available.")

# Step 9: Close connection between SUMO and Traci
traci.close()