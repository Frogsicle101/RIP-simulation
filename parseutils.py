"""
A collection of functions used in parsing the router config files

Christopher Stewart (cst141) 21069553
Frederik Markwell (fma107) 51118501
"""

import sys

def read_lines_from_file(filename):
    """
    Opens a file and reads the lines, returning a list of strings.
    If the file cannot be found or there is an error, prints a message then calls
    sys.exit
    """
    try:
        with open(filename, 'r') as config_file:
            return config_file.read().splitlines()
    except FileNotFoundError:
        print("Couldn't find", filename)
        sys.exit()
    except OSError:
        print("Error opening file")
        sys.exit()

def is_valid_int(val, min, max, name):
    """
    Checks that the given string is a valid integer between min and max
    If it is not, prints a message using name, and then calls sys.exit
    """

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
    """
    Checks that the given value is an integer, within the acceptable range,
    and not in the list of existing input_ports. Calls sys.exit if not.
    """
    if is_valid_int(port, 1024, 64000, "port") and int(port) not in existing_ports:
        return True
    print(port, "is a duplicate")
    sys.exit()

def is_valid_link(link, existing_ports):
    """
    Checks if a link (port-metric-id) is valid and formatted correctly. If not,
    calls sys.exit
    """
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
    with instance_id, input_ports, neighbour_info, and the timeout values
    """
    lines = read_lines_from_file(filename)


    id_set = False
    inputs_set = False
    outputs_set = False

    input_ports = []
    neighbour_info = []
    timeout = 180
    periodic_update_time = 30
    garbage_time = 120

    for line in lines:
        line = line.strip()
        line = line.split("#", 1)[0]
        if "router-id" in line:
            id = line.split()[1]
            if is_valid_int(id, 1, 64000, "router_id"):
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
        elif "periodic-update-time" in line:
            if is_valid_int(line.split()[1], 1, float('inf'), "periodic update time timeout"):
                periodic_update_time = int(line.split()[1])
        elif "garbage-time" in line:
            if is_valid_int(line.split()[1], 1, float('inf'), "garbage time timeout"):
                garbage_time = int(line.split()[1])
        elif "" == line:
            pass
        else:
            print("Could not process", line)
            sys.exit()



    if not all((id_set, inputs_set, outputs_set)):
        print("Need all of router-id, input-ports, outputs")
        sys.exit()
    return instance_id, input_ports, neighbour_info, timeout, periodic_update_time, garbage_time
