from pprint import pprint

from collections import deque
#insert, pop, popleft, remove, index, append


from math import inf

def adjacency_list(graph_str):
    '''g'''
    if not graph_str:
        return []
    if graph_str[-1] == "\n":
        graph_str = graph_str[:-1]#remove last \n
    data = graph_str.split("\n")
    directed = data[0].split(' ')[0] == 'D'
    n = int(data[0].split(' ')[1])
    E = [x.split(" ") for x in data[1:]]
    weighted = False
    if E:
        weighted = len(E[0]) > 2

    #print("D:", directed, "n:", n, "W:", weighted)
    #print(E)

    output = []
    for i in range(n):
        temp = []
        for j in range(len(E)):
            start_vertex = int(E[j][0])
            end_vertex = int(E[j][1])
            if start_vertex == i or end_vertex == i:
                weight = None
                if weighted:
                    weight = int(E[j][2])
                if directed and start_vertex == i:
                    temp.append((end_vertex, weight))
                elif start_vertex == i:
                    temp.append((end_vertex, weight))
                if not directed and end_vertex == i:
                    temp.append((start_vertex, weight))
        output.append(temp)

    return output


def dijkstra(adj_list, start):
    '''g'''
    n = len(adj_list)
    if n == 0:
        return [], []
    in_tree = [False for x in range(n)]
    distance = [float('inf') for x in range(n)]
    parent = [None for x in range(n)]
    distance[start] = 0
    while not all(in_tree):
        u = next_vertex(in_tree, distance)
        in_tree[u] = True
        for v, weight in adj_list[u]:
            if not in_tree[v] and (distance[u] + weight) < distance[v]:
                distance[v] = distance[u] + weight
                parent[v] = u

    return parent, distance


def next_vertex(in_tree, distance):
    '''g'''
    d = None
    for i, node_in_tree in enumerate(in_tree):
        if not node_in_tree:
            if d == None:
                d = i
            if distance[i] < distance[d]:
                d = i
    return d

def next_hop(parent, start):
    if parent[start] == None:
        return start
    elif parent[parent[start]] == None:
        return start
    return next_hop(parent,parent[start])

# 2nd number in top line is number vertices + 1
graph_string = """\
U 8 W
1 2 1
1 7 8
1 6 5
2 1 1
2 3 3
3 2 3
3 4 4
4 3 4
4 7 6
4 5 2
5 4 2
5 6 1
6 5 1
6 1 5
7 1 8
7 4 6
"""
import sys
ARGUEMENTS = sys.argv[1:]
source = int(ARGUEMENTS[0])
print(source)

parent, cost = (dijkstra(adjacency_list(graph_string), source))#forwarding table for x
print(parent[1:],cost[1:])#extra 0 vertex is included so must be removed
print("parent (p) is the last hop to the target router addr (a)")
print('a','p',"c (addr, parent(not next_hop), cost)")
for i in range(1,len(cost)):
    p = parent[i]
    if p == None:
        p = ' '
    print(i,next_hop(parent,i),cost[i])
