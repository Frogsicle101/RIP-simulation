"""

"""
import socket, os, sys, select, time

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
    print("invalid arguements given, enter arguements in the form below")
    print("filename")
    sys.exit()

class row():
    cost=1
    next_hop=0


class RIP_Router():
    table = {}
    neighbours = []
    output_ports = None
    input_ports = None
    config_file = None
    
    def close(self):
        if self.config_file:
            self.config_file.close()
        if self.rx_sockets:
            for rx_socket in self.rx_sockets:
                rx_socket.close()
        sys.exit()
    
    def __init__(self, filename):
        self.process_config_file(filename)
        self.init_input_ports()
        self.run()
        self.close()


    def create_response(self):
        '''returns a packet in the form of bytes'''
        pass
    def send_response(self, packet, addr_port):
        '''3.9.2 Response Messages'''
        pass
    
    def read_response(self,data):
        '''convert the recvd packet to a table'''
        pass
    
    def update_table(self, other_table):
        '''compare tables and update if route is better'''
        pass

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
                self.config_file = None
                self.close()              
            config_text = self.config_file.read().split("\n")
            self.config_file.close()
            print(config_text)         
            for line in config_text:
                line = line.lstrip()
                print(line)
                if "router-id" in line:
                    self.instance_id = int(line.split()[1])
                elif "input-ports" in line:
                    self.input_ports = set([int(x) for x in line[len("input-ports"):].split(",")])
                elif "outputs" in line:
                    self.output_ports = [(x) for x in line[len("outputs"):].split(",")]
            print(self.instance_id,self.input_ports,self.output_ports)
            
        else:
            print("couldnt find", filename)
            self.config_file = None
            self.close()


    def init_input_ports(self):
        '''
        Next the demon creates as many UDP sockets as it has input ports and binds one
        socket to each input port – no sockets are created for outputs, these only refer to
        input ports of neighbored routers. One of the input sockets can be used for sending
        UDP datagrams to neighbors.
        '''
        self.rx_sockets = []
        for rx_port in self.input_ports:
            try:
                rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
                rx_socket.settimeout(TIMEOUT)
                rx_socket.bind(('192.168.122.1', rx_port))
                self.rx_sockets.append(rx_socket)
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
        print("run")
        inputs = [x.fileno() for x in self.rx_sockets]
        print(inputs)     
        
        for neighbour in self.output_ports:
            packet = self.create_response()
            self.send_response(packet,0)
            
        time_remaining = 30
        while True:
            try:
                start = time()
                rlist, wlist, xlist = select.select(inputs, [], [], time_remaining)#blocks until at least one file descriptor is ready to r||w||x
                end = time()
                
                delta_time = end - start
                
                if len(rlist) != 0: #no timeout
                    time_remaining -= delta_time
                else: #timeout
                    time_remaining = 30 + random()
                    for neighbour in self.output_ports:
                        packet = self.create_response()
                        self.send_response(packet,0)                    
                    
                
                print(rlist, wlist, xlist)
                for packet in rlist:
                    #do something
                    other_table = read_response(packet)
                    update_table(other_table)
                
                self.close()
            except Exception as e:
                print(e)

    

class Client():
    server_address = None
    port_number = None
    filename = None
    port_range = (1024, 64000)
    socket = None
    file = None

    def close(self):
        if self.socket:
            self.socket.close()
        if self.file:
            self.file.close()
        sys.exit()
    
    def init_server_address(self, server_input):
        try:
            self.server_address = socket.gethostbyname(server_input)
        except:
            try:
                self.server_address = socket.getaddrinfo(server_input) #linux
            except:
                print("invalid server address. ")
                self.close()
        print(self.server_address)

    def init_port_number(self, port_number):
        port_number = int(port_number)
        if self.port_range[1] >= port_number >= self.port_range[0]:
            self.port_number = port_number
            return
        print("port number:", port_number, "out of range", self.port_range)
        self.close()

    def init_filename(self, filename):
        if os.path.isfile(filename):
            print(filename, "already exists. ")
            self.close()
        self.filename = filename

    def create_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self.socket.settimeout(TIMEOUT)
        except:
            print("failed to create socket.")
            self.close()

    def connect(self):
        try:
            self.socket.connect((self.server_address, self.port_number))
        except Exception as e:
            print('error connecting.', e)
            self.close()

    def create_file_request(self, name):
        magic_number = 0x497E.to_bytes(2, 'big')#file request number
        type_code = int(1).to_bytes(1, 'big')
        filename = name.encode('utf-8')
        if len(filename) > 1024:
            print('filename too large (> 1024 bytes)')
            self.close()
        filename_length = len(filename).to_bytes(2, 'big')
        print("created file request:", magic_number,type_code,filename_length,filename)
        return bytearray(magic_number + type_code + filename_length + filename)

    def send_file_request(self, file_request):
        try:
            self.socket.send(file_request)
        except socket.timeout:
            print("socket timed out while sending the file request")
            self.close()    
    
    def process_file_response(self):
        try:
            header = self.socket.recv(8)
        except socket.timeout:
            print('socket.timeout: timed out receiving header')
            self.close()
        
        magic_number = int.from_bytes(header[0:2], 'big')
        type_code = header[2]
        status_code = header[3]
        if status_code == 0:
            print('server could not access file')
            return
        data_length = int.from_bytes(header[4:8], 'big')
        print("file response decoded:", magic_number, type_code, status_code, data_length)
        
        try:
            self.file = open(self.filename, 'wb')
        except:
            #print(f"error creating file {self.filename}.")
            return
            
        data_written = 0
        try:
            while data_written < data_length:
                data = self.socket.recv(MAX_PACKET_SIZE)#read in next chunk if applicable
                if len(data) == 0:
                    print("error, data received is less than expected.")
                    break
                self.file.write(data)
                data_written += len(data)
        except:
            print('socket.timeout: timed out')
            return
        #print(self.filename, f"created, {data_written} bytes")


    def __init__(self, address, port, filename):
        self.init_server_address(address)
        self.init_port_number(port)
        self.init_filename(filename)
        self.create_socket()
        self.connect()
        file_request = self.create_file_request(self.filename)
        self.send_file_request(file_request)
        self.process_file_response()
        self.close()

class Server():
    name = None
    address = None
    port_number = None
    port_range = (1024, 64000)
    socket = None
    connection = None
    file = None

    def close(self):
        if self.socket:
            self.socket.close()
        if self.file:
            self.file.close()
        if self.connection:
            self.connection.close()
        sys.exit()

    def init_port_number(self, port_number):
        if self.port_range[1] >= port_number >= self.port_range[0]:
            self.port_number = port_number
            return True
        print("port number:", port_number, "out of range", self.port_range)
        self.close()

    def create_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self.name = socket.gethostname()
            self.address = socket.gethostbyname(self.name)
            self.address = ''   
            self.socket.bind((self.address, self.port_number))
     
        except:
            print("failed to create socket.")
            self.close()

    def run(self):
        while True:
            try:
                self.socket.listen()
            except:
                print('socket.listen() error.')
                self.close()
                
            self.connection, address = self.socket.accept()
            self.connection.settimeout(TIMEOUT)
            t = time.localtime()
            current_time = time.strftime("\n%H:%M:%S", t)
            print(current_time, address)

            if not self.process_file_request(self.connection, address):
                print("failed to send file.")
            else:
                print("file sent succesfully.")
            self.connection.close() 

    def process_file_request(self, connection, address):
        '''read and validate data from received packet'''
        try:
            header = connection.recv(5)
        except socket.timeout:
            print("connection timed out while receiving request.")
            return False
        
        magic_number = int.from_bytes(header[0:2], 'big')#file request number
        type_code = header[2]
        if magic_number != 0x497E or type_code != 1:
            print("invalid file request (magic no. or type code incorrect).")
            return False
        
        filename_length = int.from_bytes(header[3:5], 'big')
        if filename_length > 1024 or filename_length < 1:
            print('filename size invalid (must be > 0 and <= 1024')
            return False
        
        filename_bytes = connection.recv(filename_length)
        if len(filename_bytes) != filename_length:
            #print(f"given filename length was incorrect {filename_length}\
                  #indicated but {len(filename_bytes)} received")
            print("file len error")
            return False
        
        filename = filename_bytes.decode()
        #print(f"{filename} requested.")

        if not self.send_file_data(connection, filename):
            print("send file error")
            return False
        return True

    def send_file_data(self, connection, filename):
        '''get file data and send file response packet(s)'''        
        self.file = None
        if os.path.isfile(filename):
            try:
                self.file = open(filename, 'rb')
            except:
                #print(f'error opening and/or reading file: {filename}')
                print("couldnt open", filename)
                self.file = None
                return False
            data_len = os.path.getsize(filename)
            print("file size:{} bytes".format(data_len))
            file_response_header = self.create_file_response_header(data_len)  
            MAX_PACKET_SIZE = 4096
            data_read = 0
            connection.send(file_response_header)
            while data_read < data_len:
                data = self.file.read(MAX_PACKET_SIZE)
                try:
                    connection.send(data)
                    #print(f'{len(file_response)-8} bytes sent.')
                except socket.timeout:
                    print("failed to send file, connection timed out.")
                data_read += len(data)
        else:
            #print(f"couldn't open file {filename}")
            print("couldnt find", filename)
            data = None
            file_response_header = self.create_file_response_header(0)   
            connection.send(file_response_header)
        
         
        if self.file:
            self.file.close()
            return True
        print('unk send err')
        return False
                 
    def create_file_response_header(self, file_len):
        magic_number = 0x497E.to_bytes(2, 'big')#file request number
        type_code = int(2).to_bytes(1, 'big')
        if file_len == 0:
            status_code = int(0).to_bytes(1, 'big')
            data_length = int(0).to_bytes(4, 'big')
            return bytearray(magic_number + type_code + status_code
                         + data_length)
        status_code = int(1).to_bytes(1, 'big')
        data_length = file_len.to_bytes(4, 'big')
        return bytearray(magic_number + type_code + status_code
                         + data_length)

    def __init__(self, port_number):
        self.init_port_number(port_number)
        self.create_socket()
        self.run()
        self.socket.close()
        self.close()










def main():
    #address = ARGUEMENTS[0]
    #port = ARGUEMENTS[1]
    #filename = ARGUEMENTS[2]
    #client = Client(address, port, filename)
    filename = ARGUEMENTS[0]
    router = RIP_Router(filename)

main()

















