"""
A collection of functions used in parsing the router config files
"""

import sys

def read_lines_from_file(filename):
    with open(filename, 'r') as config_file:
        return config_file.read().splitlines()

def is_valid_int(val, min, max, name):
    if val.isdigit():
        val = int(val)
        if val >= min and val <= max:
            return True
        else:
            print(val, "is not a valid {} (must be between {} and {})".format(name, min, max))
            sys.exit()
    else:
        print(val, "is not a valid {} (non-integer)".format(name))
        sys.exit()

def is_valid_port(port, existing_ports):
	if is_valid_int(port, 1024, 64000, "port") and int(port) not in existing_ports:
		return True

def is_valid_link(link, existing_ports):
	try:
		port, cost, id = link.strip().split("-")
	except ValueError:
		print(link, "does not follow the format (port-cost-id)")
		sys.exit()

	# The below functions call sys.exit if not valid
	is_valid_port(port, existing_ports)
	is_valid_int(cost, 1, 16, "cost")
	is_valid_int(id, 1, 64000, "id")

	return True

def parse_config_file(filename):
	"""
	Reads a file as described in the assignment description and returns a tuple
	"""
	try:
		lines = read_lines_from_file(filename)
	except FileNotFoundError:
		print("Couldn't find", filename)
		sys.exit()
	except OSError:
		print("Error opening file")
		sys.exit()

	id_set = False
	inputs_set = False
	outputs_set = False

	input_ports = []
	neighbour_info = []
	timeout = 180

	for line in lines:
		line = line.strip()
		if "router-id" in line:
			id = line.split()[1]
			if is_valid_int(id, 1, 6400, "router_id"):
				instance_id = int(id)
				id_set = True

		elif "input-ports" in line:
			for port in line[len("input-ports"):].split(","):
				port = port.strip()
				if is_valid_port(port, input_ports):
					input_ports.append(int(port))
					inputs_set = True

		elif "outputs" in line:
			output_ports = [] # Keeps track so we can check for duplicates
			for link in line[len("outputs "):].split(","):
				if is_valid_link(link, input_ports + output_ports):
					port, cost, id = [int(x) for x in link.split("-")]

				neighbour_info.append((port, cost, id))
				output_ports.append(port)
			outputs_set = True
		elif "route-timeout" in line:
			if is_valid_int(line.split()[1], 1, float('inf'), "route timeout"):
				timeout = int(line.split()[1])



	if not all((id_set, inputs_set, outputs_set)):
		print("Need all of router-id, input-ports, outputs")
		sys.exit()
	return instance_id, input_ports, neighbour_info, timeout