"""
py "RIP daemon.py" "config5.txt"
"""
import socket, os, sys, select, time, random
from parseutils import parse_config_file



'''
config_file example
    router-id 1
    input-ports 6110, 6201, 7345
    outputs 5000-1-1, 5002-5-4

where input ports are the routers ports to listen to packets
and outputs = port addr to send to other routers
    e.g 5002=input port of router:4 with cost:5
'''
MAX_PACKET_SIZE = 4096

ARGUEMENTS = sys.argv[1:]
if len(ARGUEMENTS) != 1:
    ARGUEMENTS = ['config1.txt']
    #print("invalid arguements given, enter arguements in the form below")
    #print("filename")
    #sys.exit()

class Neighbour():
    '''neighbour'''
    def __init__(self):
        self.last_response_time = time.time()
        self.timer = 0

class Row():
    '''entry(value) in the routers forwarding table (dictionary) where the key is the destination router_id'''
    def __init__(self, cost, next_hop):
        self.cost = cost
        self.next_hop = next_hop
        self.last_response_time = time.time()
        self.timer = 0

    def __str__(self):
        return '(cost:'+str(self.cost)+', next_hop:'+str(self.next_hop)+')'
    def __repr__(self):
        return str(self)



class RIP_Router():
    #neighbours = {}         #dictionary with key=neighbour_router_id, value=Neighbour object
    table = {}              #dictionary with key=destination_router_id, value=Row object
    output_ports = None     #addr_port list of neighbour routers
    input_ports = None      #ports to receive packets from neighbour routers
    config_file = None
    input_sockets = None    #list of sockets, each bound to one of the input_ports
    address = None          #local computer addr
    instance_id = None      #router-id of running process
    neighbour_info = None   #info on links to neighbour routers [output_port, cost, router_id]
    garbage_time = 40      #how long until a forwarding table entry is removed since last update
    timeout = 20#180 #time (s) while no responses have been received from a neighbouring router to confirm its failure

    def close(self):
        print("Closing")
        if self.config_file:
            self.config_file.close()
        if self.input_sockets:
            for input_socket in self.input_sockets:
                input_socket.close()
        sys.exit()

    def __init__(self, filename):

        (self.instance_id,
        self.input_ports,
        self.neighbour_info,
        self.timeout) = parse_config_file(filename)

        self.init_input_ports()
        self.table[self.instance_id] = Row(0,self.instance_id)#init table with own entry
        self.print_table()
        self.run()
        self.close()


    def init_input_ports(self):
        '''
        Next the demon creates as many UDP sockets as it has input ports and binds one
        socket to each input port – no sockets are created for outputs, these only refer to
        input ports of neighbored routers. One of the input sockets can be used for sending
        UDP datagrams to neighbors.
        '''
        name = socket.gethostname()
        self.address = 'localhost'
        self.input_sockets = []
        for rx_port in self.input_ports:
            try:
                rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
                rx_socket.bind((self.address, rx_port))
                self.input_sockets.append(rx_socket)
            except Exception as e:
                print("failed to create socket.", rx_port, e)
                self.close()

    def print_table(self):
        print("Forwarding Table for {}".format(self.instance_id))
        headings = ["Address", "Next Hop", "Cost", "Timer"]
        print((" | ").join(headings))
        print("-" * sum(len(heading) + 3 for heading in headings))
        for dest, row in sorted(self.table.items(), key=lambda x: x[0]):
            timer = ""
            #print(dest,set(self.neighbours.keys()))
            if dest in self.table.keys():
                #print("test")
                timer = f"{self.table[dest].timer:.2f}"

            print("{} | {} | {} | {}".format(
                str(dest).center(len(headings[0])),
                str(row.next_hop).center(len(headings[1])),
                str(row.cost).center(len(headings[2])),
                str(timer).center(len(headings[3]))
            ))

    def create_response(self, destination):
        '''
        command(1) - version(1) - router_id(2)  #header(4)

        addr_family_id(2) - zero(2)        #each entry (20)
        ipv4_addr(4)
        zero(4)
        zero(4)
        metric(4)
        '''
        command = int(2).to_bytes(1, 'big')
        version = int(2).to_bytes(1, 'big')
        router_id = int(self.instance_id).to_bytes(2, 'big')
        zero2 = int(0).to_bytes(2, 'big')

        header = command + version + router_id#zero2 #header uses router_id instead of 16bit zero

        payload = bytes()
        for router_id in self.table.keys():#for each destination router_id
            addr_family_id = int(2).to_bytes(2, 'big')#2 = AF_INET
            ipv4_addr = int(router_id).to_bytes(4, 'big')#next_hop is the router sending the response packet
            zero4 = int(0).to_bytes(4, 'big')

            if self.table[router_id].next_hop == destination:
                metric = int(16).to_bytes(4, 'big')
            else:
                metric = int(self.table[router_id].cost).to_bytes(4, 'big')#1-15

            payload += addr_family_id + zero2 + ipv4_addr + zero4 + zero4 + metric
        result = header + payload
        return result

    def send_response(self, addr_id, addr_port):
        '''3.9.2 Response Messages'''
        packet = self.create_response(addr_id)
        target = (self.address, addr_port)
        self.input_sockets[0].sendto(bytes(packet),target)

    def send_all_responses(self):
        '''iterates all neighbour ports, and sends a response (advertisement) to each'''
        for output_port, cost, id in self.neighbour_info:
            self.send_response(id, output_port)

    def read_response(self,data):
        '''convert the recvd packet to a table, returns rId(int), table(dict)'''
        command = data[0]
        version = data[1]
        if command != 2 or version !=2:
            print("invalid command/version",command,version)
            return False,0,0#command or version value is incorrect

        router_id = int.from_bytes(data[2:4], 'big')#router(id) that sent the data

        i = 4#packet payload (RIP entries) starts after 4 bytes
        if (len(data)-4) % 20 != 0 or len(data) <= 4:
            print("invalid packet length", len(data))
            return False,0,0#data length incorrect (should be 4 + 20x) where x > 0

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
                metric = int.from_bytes(data[i:i+4], 'big')# between 1-5 (inclusive) or 16 (inf)
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
        '''gets cost to travel to a particular neighbouring router'''
        neighbour_ids = [x[2] for x in self.neighbour_info]#TODO use neighbours dict with Neighbour objects to replace neighbour_info and output_ports
        cost = self.neighbour_info[neighbour_ids.index(router_id)][1]
        return cost

    def update_table(self, other_router_id, other_table):
        '''compare tables and update if route is better'''
        cost = self.cost_to_neighbour(other_router_id)
        send_triggered_update = False
        for dest in other_table.keys():
            #todo CHECK IF COST IS 16
            other_row = other_table[dest]

            try:

                current_row = self.table[dest]

                from_authority = self.table[dest].next_hop == other_router_id
                cost_changed = current_row.cost != min(16, other_row.cost + cost)

                if from_authority:
                    if cost_changed:
                        self.update_row(dest, cost, other_row, other_router_id)
                        if cost + other_row.cost >= 16:
                            send_triggered_update = True
                    else:
                        if current_row.cost != 16:
                            self.update_row(dest, cost, other_row, other_router_id)


                    # Our current route comes from this router, so must take their value


                    if cost_changed and cost + other_row.cost >= 16:
                        send_triggered_update = True

                elif current_row.cost > (other_row.cost + cost):

                    #current route less optimal than jump_to_neighbour + neighbours_route

                    self.update_row(dest, cost, other_row, other_router_id)

            except KeyError:#means we currently do not have a route to this dst (dest)

                if other_table[dest].cost + cost < 16: # Ignore routes with cost of 16
                    self.update_row(dest, cost, other_row, other_router_id)

        if send_triggered_update:
            self.send_all_responses()
        self.print_table()

    def update_row(self, dest, cost, other_row, other_router_id):
        row = Row(min(16, other_row.cost + cost), other_router_id)
        self.table[dest] = row

        self.table[dest].last_response_time = time.time()
        self.table[dest].timer = 0.00

    def run(self):
        '''
        Finally, you will enter an infinite loop in which you react to incoming events (check
        out the select() system call and its equivalent in Python.1)
        An incoming event is either:
            a routing packet received from a peer (upon which you might need to
            update your own routing table, print it on the screen, or possibly send own routing
            messages to your peers),

            or it is a timer event upon which you send an unsolicited RIP response message to
            your peers.

        Please ensure that you handle each event
        atomically, i.e. the processing of one event (e.g. a received packet) must not be
        interrupted by processing another event (e.g. a timer).
        '''
        print("\n\nrun\n\n")
        inputs = [x.fileno() for x in self.input_sockets]
        #print(inputs)

        self.send_all_responses()

        random_range = 2#should be 10 when we finished

        time_remaining_constant = 10
        time_remaining = time_remaining_constant
        while True:
            try:
                start = time.time()
                rlist, wlist, xlist = select.select(inputs, [], [], time_remaining)#blocks until at least one file descriptor is ready to r||w||x
                end = time.time()
                #print(rlist, wlist, xlist)
                delta_time = end - start

                #add time waited to each routes timer
                routes_to_del = []
                for key in self.table.keys():
                    if key != self.instance_id:#don't increase timer of own route
                        self.table[key].timer = time.time() - self.table[key].last_response_time
                        if self.table[key].timer > self.timeout:
                            self.table[key].cost = 16
                        if self.table[key].timer > self.garbage_time:
                            routes_to_del.append(key)
                for route in routes_to_del:
                    del self.table[route]#removes entry from table



                #print('delta_time:',delta_time)
                if len(rlist) != 0: #no timeout
                    print("received packets ready to be read in socket ids:",rlist)
                    time_remaining = max(0, time_remaining - delta_time)
                else: #timeout
                    time_remaining = time_remaining_constant + (random.random()*random_range) - random_range/2
                    self.send_all_responses()
                    self.print_table()

                try:
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

                except Exception as e:#except to ignore the error
                    print(e)
                    #[WinError 10054] An existing connection was forcibly closed
                    pass
            except Exception as e:
                print(e)
                self.close()
        self.close()


def main():
    filename = ARGUEMENTS[0]
    router = RIP_Router(filename)

main()
