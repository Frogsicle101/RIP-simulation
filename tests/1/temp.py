#just changed command to 2 instead of 1
def create_response(self, destination):
    '''
    command(1) - version(1) - router_id(2)  #header(4)

    addr_family_id(2) - zero(2)        #each entry (20)
    ipv4_addr(4)
    zero(4)
    zero(4)
    metric(4)
    '''
    command = int(2).to_bytes(1, 'big')#1 for req, 2 for response
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



def read_response(self,data):
    '''convert the recvd packet to a table, returns rId(int), table(dict)'''
    command = data[0]
    version = data[1]
    if command != 2 or version !=2:
        return False,0,0#command or version value is incorrect
    
    router_id = int.from_bytes(data[2:4], 'big')#router(id) that sent the data
   
    i = 4#packet payload (RIP entries) starts after 4 bytes   
    if (len(data)-4) % 20 != 0 or len(data) <= 4:
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

            if min(zeros) != 0 or max(zeros) != 0 or metric < 1 or metric > 16:
                return False,0,0#bad RIP entry            
        except IndexError:
            return False,0,0#data length incorrect (should be 4 + 20x)
    return True, router_id, recvd_table

#in run function
packet_valid, other_router_id, other_table = self.read_response(data)
if packet_valid:
    self.update_table(other_router_id, other_table)
