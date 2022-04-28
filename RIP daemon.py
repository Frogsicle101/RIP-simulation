"""
py "RIP daemon.py" "config2.txt"
"""
import socket, os, sys, select, time, random

MAX_PACKET_SIZE = 4096 #maximum packet size in bytes to avoid memory/RAM issues
TIMEOUT = 15 #timeout for sockets in seconds


'''
config_file example
    router-id 1
    input-ports 6110, 6201, 7345
    outputs 5000-1-1, 5002-5-4

where input ports are the routers ports to listen to packets
and outputs = port addr to send to other routers
    e.g 5002=input port of router:4 with cost:5
'''


ARGUEMENTS = sys.argv[1:]
if len(ARGUEMENTS) != 1:
    ARGUEMENTS = ['config1.txt']
    #print("invalid arguements given, enter arguements in the form below")
    #print("filename")
    #sys.exit()

class Row():
    cost=1
    next_hop=None       #next hop router_id
    last_confirmation_time=None          # TODO time since last updated (from neighbours, excluding self info),
                                         # needs to be checked to confirm it is still valid (<180s)
    def __init__(self, cost, next_hop):
        self.cost = cost
        self.next_hop = next_hop
        self.timer = time.time()
    def __str__(self):
        return '(cost:'+str(self.cost)+', next_hop:'+str(self.next_hop)+')'
    def __repr__(self):
        return str(self)



class RIP_Router():
    table = {}              #dictionary with key=destination_port, value=row object
    output_ports = None     #addr_port list of neighbour routers
    input_ports = None      #ports to receive packets from neighbour routers
    config_file = None
    input_sockets = None    #list of sockets, each bound to one of the input_ports
    address = None          #local computer addr
    instance_id = None      #router-id of running process
    neighbour_info = None   #info on links to neighbour routers [output_port, cost, router_id]

    def close(self):
        if self.config_file:
            self.config_file.close()
        if self.input_sockets:
            for input_socket in self.input_sockets:
                input_socket.close()
        sys.exit()

    def __init__(self, filename):
        self.process_config_file(filename)
        self.init_input_ports()
        self.table[self.instance_id] = Row(0,self.instance_id)#init table with own entry
        self.print_table()
        self.run()
        self.close()

    def print_table(self):
        print("Forwarding Table for {}".format(self.instance_id))
        headings = ["Address", "Next Hop", "Cost"]
        print((" | ").join(headings))
        print("-" * sum(len(heading) + 3 for heading in headings))
        for dest, row in sorted(self.table.items(), key=lambda x: x[0]):
            print("{} | {} | {}".format(
                str(dest).center(len(headings[0])),
                str(row.next_hop).center(len(headings[1])),
                str(row.cost).center(len(headings[2]))
            ))

    def create_response(self):
        '''
        command(1) - version(1) - router_id(2)  #header(4)

        addr_family_id(2) - zero(2)        #each entry (20)
        ipv4_addr(4)
        zero(4)
        zero(4)
        metric(4)
        '''
        command = int(1).to_bytes(1, 'big')
        version = int(2).to_bytes(1, 'big')
        router_id = int(self.instance_id).to_bytes(2, 'big')
        zero2 = int(0).to_bytes(2, 'big')

        header = command + version + router_id#zero2 #header uses router_id instead of 16bit zero

        payload = bytes()
        for router_id in self.table.keys():#for each destination router_id
            addr_family_id = int(2).to_bytes(2, 'big')#2 = AF_INET
            ipv4_addr = int(router_id).to_bytes(4, 'big')#next_hop is the router sending the response packet
            zero4 = int(0).to_bytes(4, 'big')
            metric = int(self.table[router_id].cost).to_bytes(4, 'big')#1-15
            payload += addr_family_id + zero2 + ipv4_addr + zero4 + zero4 + metric
        result = header + payload
        return result

    def send_response(self, addr_port):
        '''3.9.2 Response Messages'''
        packet = self.create_response()
        target = (self.address, addr_port)
        self.input_sockets[0].sendto(bytes(packet),target)

    def send_all_responses(self):
        '''iterates all neighbour ports, and sends a response (advertisement) to each'''
        for output_port in self.output_ports:
            self.send_response(output_port)

    def read_response(self,data):
        '''convert the recvd packet to a table, returns rId(int), table(dict)'''
        try:
            command = data[0]#int.from_bytes(data[0], 'big')
            version = data[1]#int.from_bytes(data[1], 'big')
            router_id = int.from_bytes(data[2:4], 'big')#router(id) that sent the data
        except Exception as e:
            print(e)
        recvd_table = {}
        i = 4#packet payload starts after 4 bytes
        while i < len(data):
            try:
                addr_family_id = int.from_bytes(data[i:i+2], 'big')
                i+=4
                ipv4_addr = int.from_bytes(data[i:i+4], 'big')#dest addr from the router sending
                i+=12
                metric = int.from_bytes(data[i:i+4], 'big')
                row = Row(metric, router_id)#cost, next_hop, instance_id
                recvd_table[ipv4_addr] = row
                i+=4
            except IndexError:
                break
        return router_id, recvd_table

    def update_table(self, other_router_id, other_table):
        '''compare tables and update if route is better'''
        neighbour_ids = [x[2] for x in self.neighbour_info]
        cost = self.neighbour_info[neighbour_ids.index(other_router_id)][1]
        for key in other_table.keys():
            try:
                current_row = self.table[key]
                #check if other_table has better route
                other_row = other_table[key]
              
            except KeyError:
                row = other_table[key]
                row.next_hop = other_router_id#next_hop is the router sending the advertisement
                row.cost += cost#cost to the router sending the advertisement + its own cost to reach dst
                self.table[key] = row
        print("Updated table")
        self.print_table()

    def process_config_file(self, filename):
        '''
        reads a configuration file (name supplied as a command line parameter)
            -contains a unique identification for the routing demon instance,
            -the port numbers on which the demon receives routing packets from peer demons (input ports),
            -and specifications of the outputs towards neighbored routers.

        Clearly, any output port declared for one router should be an input port of another router. The
        information in the configuration file is only meant to inform demons about links,
        the demons internal routing table must not be initialized from the configuration
        file.
        '''
        self.config_file = None
        if os.path.isfile(filename):
            try:
                self.config_file = open(filename, 'r')
            except Exception as e:
                print("couldnt open", filename, e)
                self.close()
            config_text = self.config_file.read().split("\n")
            self.config_file.close()
            print("config file lines:",config_text)
            for line in config_text:
                line = line.lstrip()
                if "router-id" in line:
                    self.instance_id = int(line.split()[1])
                elif "input-ports" in line:
                    self.input_ports = [int(x) for x in line[len("input-ports"):].split(",")]
                elif "outputs" in line:
                    self.output_ports = [int(x.split('-')[0]) for x in line[len("outputs "):].split(",")]     #7002
                    self.neighbour_info = [(x.split('-')) for x in line[len("outputs "):].split(",")]   #7002-1-1 (port,cost,id)
                    for i, entry in enumerate(self.neighbour_info):
                        for j, number in enumerate(self.neighbour_info[i]):
                            self.neighbour_info[i][j] = int(self.neighbour_info[i][j])
                    print("neighbour_info",self.neighbour_info)
        else:
            print("couldnt find", filename)
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
                rx_socket.settimeout(TIMEOUT)
                rx_socket.bind((self.address, rx_port))
                self.input_sockets.append(rx_socket)
            except Exception as e:
                print("failed to create socket.", rx_port, e)
                self.close()

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
                #print('delta_time:',delta_time)
                if len(rlist) != 0: #no timeout
                    print("received packets ready to be read in socket ids:",rlist)
                    time_remaining -= delta_time
                else: #timeout
                    time_remaining = time_remaining_constant + (random.random()*random_range) - random_range/2
                    self.send_all_responses()

                try:
                    '''reads responses (if any) from neighbours and updates tables'''
                    for socket_id in rlist:
                        sock = socket.fromfd(socket_id,socket.AF_INET, socket.SOCK_DGRAM)
                        #print(sock)
                        data = sock.recv(MAX_PACKET_SIZE)
                        #exit(1)
                        other_router_id, other_table = self.read_response(data)
                        self.update_table(other_router_id, other_table)
                except Exception as e:
                    #print(e)
                    pass
            except Exception as e:
                print(e)
                self.close()
        self.close()


def main():
    filename = ARGUEMENTS[0]
    router = RIP_Router(filename)

main()
