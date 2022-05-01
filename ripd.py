"""
An implementation of the RIP routing protocol for COSC364 Assignment 1
Routes using router-ids instead of network addresses

Christopher Stewart (cst141) 21069553
Frederik Markwell (fma107) 51118501
"""

import socket, os, sys, select, time, random
from parseutils import parse_config_file

# Sets the maximum size packet that the router can receive
MAX_PACKET_SIZE = 4096

# Changes how the router prints out its table. If PRETTY, prints as often as
# possible, clearing the screen. If not, prints only when there is an update
# and does not clear the screen.
PRETTY = True

class Row():
    """
    Entry in the routers forwarding table (dictionary) where the key is the
    destination router_id. A new row is created whenever the route is updated
    """
    def __init__(self, cost, next_hop):
        self.cost = cost
        self.next_hop = next_hop
        self.last_response_time = time.time()
        self.timer = 0

        self.changed = True # Set false when a packet is sent containing this row
    def __str__(self):
        return '(cost:' + str(self.cost) + ', next_hop:' + str(self.next_hop) + ')'
    def __repr__(self):
        return str(self)



class RIP_Router():
    """
    The main router class. Calls self.run on init, which enters an infinte loop.
    The infinite loop sends an update message every 30 s, and waits for incoming
    messages, which it uses to update its forwarding table
    """
    # Dictionary with key=destination_router_id, value=Row object
    table = {}

    # List of sockets, each bound to one of the input_ports
    input_sockets = None

    # Local computer address
    address = 'localhost'

    # Router-id of running process
    instance_id = None

    # List of info on links to neighbour routers
    # Composed of tuples (output_port, cost, router_id)
    neighbour_info = None

    # Timer to keep track of whether a triggered update has been sent recently
    # Helps prevent network congestion
    triggered_update_timer = 0

    # If the triggered_update_timer reaches 0 and this is True, will send a triggered update
    triggered_update_waiting = False


    def close(self):
        """
        Closes all sockets and exits the program
        """
        print("Closing")
        if self.input_sockets:
            for input_socket in self.input_sockets:
                input_socket.close()
        sys.exit()


    def __init__(self, filename):
        """
        Parses the provided configuration file and sets all configurable
        variables. Creates sockets, initial forwarding table, and then
        listens in a loop for other RIP daemons
        """
        (self.instance_id,
        input_ports,
        self.neighbour_info,
        self.timeout,
        self.periodic_update_time,
        self.garbage_time) = parse_config_file(filename)

        self.garbage_time += self.timeout

        self.init_input_ports(input_ports)

        #init table with own entry
        self.table[self.instance_id] = Row(0,self.instance_id)

        self.print_table()

        self.run()
        self.close()


    def init_input_ports(self, input_ports):
        """
        Creates a socket for each input port provided in the configuration file
        and binds them to localhost
        """
        self.input_sockets = []
        for rx_port in input_ports:
            try:
                rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
                rx_socket.bind((self.address, rx_port))
                self.input_sockets.append(rx_socket)
            except Exception as e:
                print("failed to create socket.", rx_port, e)
                self.close()

    def print_table(self):
        """
        Prints the forwarding table to the console
        """
        print("\n" + "-" * 30)
        print("Forwarding Table for {}".format(self.instance_id))
        headings = ["Address", "Next Hop", "Cost", "Timer", "Change"]
        print((" | ").join(headings))
        print("-" * sum(len(heading) + 3 for heading in headings))
        for dest, row in sorted(self.table.items(), key=lambda x: x[0]):
            timer = ""
            if dest in self.table.keys():
                timer = f"{self.table[dest].timer:.2f}"

            print("{} | {} | {} | {} | {}".format(
                str(dest).center(len(headings[0])),
                str(row.next_hop).center(len(headings[1])),
                str(row.cost).center(len(headings[2])),
                str(timer).center(len(headings[3])),
                str(row.changed).center(len(headings[4]))
            ))


    def create_response(self, destination, triggered):
        """
        Creates a RIP response packet for the destination router in
        the below format

        command(1) - version(1) - router_id(2)  #header(4)

        addr_family_id(2) - zero(2)             #each entry (20)
        ipv4_addr(4)
        zero(4)
        zero(4)
        metric(4)
        """
        command = int(2).to_bytes(1, 'big')
        version = int(2).to_bytes(1, 'big')
        router_id = int(self.instance_id).to_bytes(2, 'big')
        zero2 = int(0).to_bytes(2, 'big')
        header = command + version + router_id # header uses router_id instead of 16bit zero

        payload = bytes()
        for router_id in self.table.keys(): # for each destination router_id
            if not triggered or self.table[router_id].changed:
                # Only send all routes if not triggered update

                addr_family_id = int(2).to_bytes(2, 'big') # 2 = AF_INET
                ipv4_addr = int(router_id).to_bytes(4, 'big') # next_hop is the router sending the response packet
                zero4 = int(0).to_bytes(4, 'big')


                if self.table[router_id].next_hop == destination:
                    # Route goes through the router we are sending to, should poison
                    metric = int(16).to_bytes(4, 'big')
                else:
                    # No need to poison
                    metric = int(self.table[router_id].cost).to_bytes(4, 'big')
                payload += addr_family_id + zero2 + ipv4_addr + zero4 + zero4 + metric
        result = header + payload
        return bytearray(result)

    def send_response(self, addr_id, addr_port, triggered):
        """
        Creates and sends a response / triggered update to a specific router
        """
        packet = self.create_response(addr_id, triggered)
        target = (self.address, addr_port)
        self.input_sockets[0].sendto(bytes(packet),target)

    def send_all_responses(self, triggered=False):
        """
        Iterates all neighbour ports, and sends a response / triggered update to each
        """

        # If we send a normal message, we don't need to send a triggered update later
        self.triggered_update_waiting = False

        for output_port, cost, id in self.neighbour_info:
            self.send_response(id, output_port, triggered)

        # Routes are no longer considered "new" once we have sent them out
        for row in self.table.values():
            row.changed = False

    def read_response(self,data):
        """
        Converts the received packet to a table if it follows the correct format
        returns (packet_valid(bool), router_id(int), table(dict))
        """
        command = data[0]
        version = data[1]
        if command != 2 or version !=2:
            print("invalid command/version",command,version)
            return False, 0, 0 # command or version value is incorrect

        router_id = int.from_bytes(data[2:4], 'big') # router(id) that sent the data

        i = 4 # packet payload (RIP entries) starts after 4 bytes
        if (len(data)-4) % 20 != 0 or len(data) <= 4:
            print("invalid packet length", len(data))
            return False,0,0 # data length incorrect (should be 4 + 20x) where x > 0

        recvd_table = {}
        while i < len(data):
            try:
                zeros = []#append all expected zero values here to validate packet
                addr_family_id = int.from_bytes(data[i:i+2], 'big')
                i+=2
                zeros.append(int.from_bytes(data[i:i+2], 'big'))#zero2
                i+=2
                ipv4_addr = int.from_bytes(data[i:i+4], 'big')#dest addr from the router sending
                i+=4
                zeros.append(int.from_bytes(data[i:i+4], 'big'))#zero4
                i+=4
                zeros.append(int.from_bytes(data[i:i+4], 'big'))#zero4
                i+=4
                metric = int.from_bytes(data[i:i+4], 'big')# between 1-15 (inclusive) or 16 (inf)
                row = Row(metric, router_id)#cost, next_hop
                recvd_table[ipv4_addr] = row
                i+=4

                if min(zeros) != 0 or max(zeros) != 0 or metric < 0 or metric > 16:
                    print("invalid RIP ENTRY format", zeros,metric)
                    return False,0,0#bad RIP entry
            except IndexError:
                print("index error", i, len(data))
                return False,0,0#data length incorrect (should be 4 + 20x)
        return True, router_id, recvd_table

    def cost_to_neighbour(self, router_id):
        """
        Calculates cost to travel to a particular neighbouring router
        """
        neighbour_ids = [x[2] for x in self.neighbour_info]
        cost = self.neighbour_info[neighbour_ids.index(router_id)][1]
        return cost

    def update_table(self, other_router_id, other_table):
        """
        Compares tables with a received table and updates if
            1. A route is better than the current route
                or
            2. The route comes from the router from which the the old route
                came (here called the authority)
        When a route is updated, the timer on that route is also updated. Timers
        are not updated if the authority repeatedly reports that the cost is 16
        (so that route may timeout)
        """
        cost = self.cost_to_neighbour(other_router_id)
        for dest in other_table.keys():
            other_row = other_table[dest]

            try:
                current_row = self.table[dest]
                from_authority = self.table[dest].next_hop == other_router_id
                cost_changed = current_row.cost != min(16, other_row.cost + cost)

                if from_authority:
                    # Our current route comes from this router, so must take their value
                    if cost_changed:
                        # Change our table to match the authority
                        self.update_row(dest, cost, other_row, other_router_id)
                        if cost + other_row.cost >= 16:
                            self.triggered_update_waiting = True
                    elif current_row.cost != 16:
                        # Resets the timer for reachable routes (to keep it alive)
                        self.table[dest].last_response_time = time.time()
                        self.table[dest].timer = 0.00
                elif current_row.cost > (other_row.cost + cost):
                    # The current route is less optimal than the jump to the neighbour + the neighbours route
                    self.update_row(dest, cost, other_row, other_router_id)

            except KeyError: # We currently do not have a route to this dest
                if other_table[dest].cost + cost < 16: # Ignore routes with cost > 16
                    self.update_row(dest, cost, other_row, other_router_id)

        self.print_table()

    def update_row(self, dest, cost, other_row, other_router_id):
        """
        Replaces an existing route with a route from a row in another table and
        resets the timer on that route
        """

        row = Row(min(16, other_row.cost + cost), other_router_id)
        self.table[dest] = row

        self.table[dest].last_response_time = time.time()
        self.table[dest].timer = 0.00


    def update_table_timers(self):
        """
        Add time waited to each routes timer, if necessary timeout or delete the route
        """
        routes_to_del = []
        for key in self.table.keys():
            if key != self.instance_id:#don't increase timer of own route
                self.table[key].timer = time.time() - self.table[key].last_response_time#update routes timer
                if self.table[key].timer > self.timeout and self.table[key].cost != 16:#route timed out
                    self.table[key].cost = 16
                    self.table[key].changed = True
                    self.triggered_update_waiting = True
                    self.print_table()
                if self.table[key].timer > self.garbage_time:#route deleted
                    routes_to_del.append(key)

        # We delete all the routes together so that we don't alter the indicies while looping through
        for route in routes_to_del:
            del self.table[route]#removes entry from table

        if len(routes_to_del) > 0:#if a route is deleted due to garbage collection, print updated table
            self.print_table()




    def run(self):
        """
        Enters an infinite loop in which the router reacts to incoming events
        An incoming event is either:
            a routing packet received from a peer
            a timer event
        """

        inputs = [x.fileno() for x in self.input_sockets]

        self.send_all_responses()

        random_range = self.periodic_update_time * 0.4

        response_timer = self.periodic_update_time

        while True:
            try:

                start = time.time()

                rlist, wlist, xlist = select.select(inputs, [], [], 0.1 if PRETTY else 0.01)


                if response_timer <= 0:
                    response_timer = self.periodic_update_time + (random.random()*random_range) - random_range / 2
                    self.send_all_responses()
                    self.print_table()


                self.update_table_timers()


                if self.triggered_update_timer == 0 and self.triggered_update_waiting:
                    self.send_all_responses(triggered=True)
                    self.triggered_update_waiting = False
                    self.triggered_update_timer = 1 + random.random() * 4
                    print("Sent a triggered update!")


                '''reads responses (if any) from neighbours and updates tables'''
                for socket_id in rlist:
                    sock = socket.fromfd(socket_id,socket.AF_INET, socket.SOCK_DGRAM)
                    data = sock.recv(MAX_PACKET_SIZE)
                    packet_valid, other_router_id, other_table = self.read_response(data)
                    print("Received packet from", other_router_id)
                    if packet_valid:
                        self.update_table(other_router_id, other_table)
                    else:
                        print("invalid packet")


                end = time.time()
                delta_time = end - start

                response_timer = max(0, response_timer - delta_time)
                self.triggered_update_timer = max(0, self.triggered_update_timer - delta_time)

                if PRETTY:
                    os.system("clear")
                    self.print_table()


            except Exception as e:
                print("An unexpected error occurred [{}]".format(e))
                self.close()
        self.close()


def main():
    arguments = sys.argv[1:]
    if len(arguments) != 1:
        print("Invalid arguments given, must include the directory of a valid configuration file")
        sys.exit()
    filename = arguments[0]
    router = RIP_Router(filename)



main()
