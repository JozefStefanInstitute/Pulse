from math import inf

import requests
import copy
from ..vrp import VRP
from ...create_graph.config.config_parser import ConfigParser
from ...utils.structures.deliveries import Deliveries
from ...utils.structures.node import Node
from ...utils.structures.parcel import Parcel
from ...utils.structures.plan import Plan
from ...utils.structures.vehicle import Vehicle
from ...utils.clo_update_handler import CloUpdateHandler


url = "https://graphhopper.com/api/1/vrp?key=e8a55308-9419-4814-81f1-6250efe25b5c"

ELTA_USE_CASE = "ELTA"
SLO_CRO_USE_CASE = "SLO-CRO"
CROATIA = "CRO"
SLOVENIA = "SLO"

config_parser = ConfigParser()
import numpy as np


class VrpProcessor:
    """Processes a request for routing
        Many operations on lists in this code can be replaced with dicts or similar, to remove list iteration with
        dict lookup.
    """

    def __init__(self, graphs, use_case):
        self.vrp = VRP()
        self.graphs = graphs
        self.use_case = use_case

    def map_vehicles(self, vehicles):
        """Assign vehicles to partitions"""
        map_v = [[] for _ in self.graphs]

        for v in vehicles:
            for i in range(len(self.graphs)):
                graph = self.graphs[i]
                for node in graph.nodes:
                    if v.start_node == node.id:
                        map_v[i].append(v)
        return map_v

    def map_deliveries(self, deliveries):
        """Assign deliveries to partitions"""
        delivery_parts = [[] for _ in self.graphs]
        for d in deliveries:
            for i in range(len(self.graphs)):
                graph = self.graphs[i]
                nodes = graph.nodes
                for n in nodes:
                    if n.id == d.target:
                        delivery_parts[i].append(d)
        print(sum([len(x) for x in delivery_parts]), len(deliveries))
        # TODO: THis doesnt pass, because the len of expected deliveries is
        # less than the number of deliveries now when brokenVehicle event occurred.
        # Needs to be fixed.
        # assert sum([len(x) for x in delivery_parts]) == len(deliveries)
        return delivery_parts

    @staticmethod
    def map_dropoff(graph, deliveries):
        """Computer VRP input vector, how much volume will be dropped off on each node"""
        dropoff = [0] * len(graph.nodes)
        for d in deliveries:
            node = graph.node_from_id(d.target)
            idx = graph.nodes.index(node)
            dropoff[idx] += d.volume
        return dropoff

    @staticmethod
    def map_start_nodes(graph, vehicles):
        """Compute VRP input list of vectors where do the vehicles start"""
        indexes = []
        for v in vehicles:
            index = []
            for i in range(len(graph.nodes)):
                if graph.nodes[i].id == v.start_node:
                    index.append(i)
                for parcel in v.parcels:
                    if graph.nodes[i].id == parcel.target:
                        index.append(i)
            indexes.append(index)
        return indexes

    def process(self, vehicles, deliveries_object, event_type, use_case_graph):
        """Process routing request with N vehicles and M deliveries, to produce a list of routing plans"""
        deliveries_all = deliveries_object.origin + deliveries_object.req
        deliveries_req = deliveries_object.req

        # Handle SLO-CRO use case for mapping vehicles and deliveries
        if self.use_case == SLO_CRO_USE_CASE:
            delivery_map = self.map_slo_cro_deliveries(deliveries_all, event_type)
            delivery_map_req = self.map_slo_cro_deliveries(deliveries_req, event_type)
            vehicle_map = self.map_slo_cro_vehicles(vehicles, event_type)

            # Slightly modified for SLO-CRO use case, because we only have 1 graph, but two Countries which should
            # be treated as two plans.
            plans = [Plan(vehicle_map[i], delivery_map[i], delivery_map_req[i], self.graphs[0]) for i in
                     range(2)]
        else:
            delivery_map = self.map_deliveries(deliveries_all)
            delivery_map_req = self.map_deliveries(deliveries_req)
            vehicle_map = self.map_vehicles(vehicles)

            # mapping all data to partitions
            plans = [Plan(vehicle_map[i], delivery_map[i], delivery_map_req[i], self.graphs[i]) for i in
                     range(len(self.graphs))]

        routes = []
        for i, plan in enumerate(plans):
            partition = plan.partition
            if len(plan.deliveries) == 0 or len(plan.vehicles) == 0:
                print('Skipping plan {}, no deliveries or vehicles assigned'.format(i))
                continue
            else:
                print("Computing routing for plan", i)
            print('Starting planning for {} vehicles to deliver {} packages. Node len: {}'.format(len(plan.vehicles),
                                                                                                  len(plan.deliveries),
                                                                                                  len(partition.nodes)))

            # compute input vectors
            dropoff = self.map_dropoff(plan.partition, plan.deliveries)
            print("dropoff", dropoff)
            capacity = [v.capacity for v in plan.vehicles]
            start_loc = self.map_start_nodes(partition, plan.vehicles)
            costs = [e.cost for e in partition.edges]

            # ============================================================================================
            # MODIFICATION FOR STOPAR'S VRP
            # ============================================================================================

            # Only one vehicle per plan
            indexes = []
            for v in plan.vehicles:
                for i in range(len(partition.nodes)):
                    if partition.nodes[i].id == v.start_node:
                        indexes.append(i)
            start_loc_stopar = indexes

            # Cost matrix per kilometer
            cost_matrix = []
            for vehicle in plan.vehicles:
                for edge in partition.edges:
                    cost_matrix.append(edge.cost/1000) # to kms
            new_cost_matrix = cost_matrix #+ cost_matrix

            """Build incidence matrix for LS VRP instance"""
            incident_matrix = []
            graph = plan.partition

            for ni, n in enumerate(graph.nodes):
                tmp_arr = [0] * len(graph.edges)
                for ne, e in enumerate(graph.edges):
                    if e.start == n.id:
                        tmp_arr[ne] = -1
                    elif e.end == n.id:
                        tmp_arr[ne] = 1
                tmp_arr_neg = np.negative(tmp_arr).tolist()
                incident_matrix.append(tmp_arr)

            req_json = {}
            req_json['startV'] = start_loc_stopar
            req_json['endV'] = start_loc_stopar
            req_json['vehicleCapacityV'] = capacity
            req_json['nodeDistributionV'] = dropoff

            edge_vector = [edge.cost/(60*1000) for edge in partition.edges]
            req_json['edgeTimeV'] = edge_vector# + edge_vector
            req_json['nodeOpenV']= [0 for _ in partition.nodes] # from 0
            req_json['nodeCloseV']= [16 for _ in partition.nodes] # to 16
            req_json['costMat'] = new_cost_matrix
            req_json["incidenceMat"] = incident_matrix

            computed_routes, costs = self.vrp.vrp(req_json)
            dispatch = dropoff

            # ====================================================================================
            # END
            # ====================================================================================

            # TODO: uncomment to use MIHA's VRP
            # computed_routes, dispatch, objc = self.vrp.vrp(partition.incident_matrix, dropoff, capacity, start_loc, costs)

            # compute routes based on dispatch vectors from VRP. Since VRP output is incomplete/not best,
            # we add A* routing on top
            plan_routes = self.make_route(dispatch, partition, plan.vehicles, plan.deliveries_req, event_type, use_case_graph)
            routes += plan_routes

        return routes

    @staticmethod
    def find_closest_post(loads, start, graph):
        nodes = graph.nodes
        min_dist = inf
        min_idx = -1

        for post_idx, load in enumerate(loads):
            if load > 0:
                cur_dist = graph.distance(start, nodes[post_idx])
                if cur_dist < min_dist:
                    min_dist = cur_dist
                    min_idx = post_idx
        return min_idx

    @staticmethod
    def make_route_sequence(route):
        cluster = route[0].cluster
        nodes_seq = {"vehicles": [{
            "vehicle_id": route[0].id,
            "start_address": {
                "location_id": route[0].name,
                "lon": route[0].lon,
                "lat": route[0].lat
            }
        }]
        }
        nodes = []
        for node in route[1:]:
            e = {
                "id": node.id,
                "name": "coglo",
                "address": {
                    "location_id": node.name,
                    "lon": node.lon,
                    "lat": node.lat
                }
            }
            nodes.append(e)
        nodes_seq['services'] = nodes
        import json
        payload = json.dumps(nodes_seq)
        headers = {'Content-Type': 'application/json'}
        response = requests.request("POST", url, headers=headers, data=payload)
        response_json = response.json()
        reordered_list = []
        reordered_list.append(Node({'uuid': route[0].id,
                       'address': route[0].name,
                       'lat': route[0].lat,
                       'lon': route[0].lon,
                       'cluster': cluster}))
        if len(response_json['solution']['routes'][0]['activities']) > 2:
            for route_point in response_json['solution']['routes'][0]['activities'][1:-1]:
                reordered_list.append(Node({'uuid': route_point['id'],
                               'address': route_point['address']['location_id'],
                               'lat': route_point['address']['lat'],
                               'lon': route_point['address']['lon'],
                               'cluster': cluster}))
            return reordered_list
        else:
            return route

    def make_route(self, loads, graph, vehicles, deliveries_req, event_type, use_case_graph):
        nodes = graph.nodes
        edges = graph.edges
        print("Building route from VRP output...")
        start_nodes = [graph.node_from_id(x.start_node) for x in vehicles]

        routes = []
        converted_routes = []
        loads_new = []
        vehicle_node_sequence = []

        # update list of vehicle parcels: add new parcels to vehicle.parcels list)
        # exception: crossborder - as the mapping of parcels on the nodes change. We keep the final list not updated
        for x, vehicle in enumerate(vehicles):
            load = loads[x]
            load = [int(x) for x in load]
            loads_origin = self.map_dropoff(graph, vehicle.parcels)
            if event_type != "crossBorder":
                for i in range(len(nodes)):     # add new parcels to the vehicle from the orders
                    vehicle_load_diff = load[i] - loads_origin[i]

                    while vehicle_load_diff > 0:
                        for j in range(len(deliveries_req)):
                            if deliveries_req[j].target == nodes[i].id:

                                # Payweight needs to be decreased from vehicle_load_diff, because it
                                # drops all packets for one location at once
                                pay_weight = deliveries_req[j].volume

                                vehicle.parcels.append(deliveries_req[j])
                                deliveries_req.remove(deliveries_req[j])
                                vehicle_load_diff -= pay_weight
                                break

            loads_new.append(self.map_dropoff(graph, vehicle.parcels))

        for i, vehicle_load in enumerate(loads_new):
            start_node = start_nodes[i]
            route = [start_node]
            vehicle_node_sequence.append(start_node.id)

            current_node = start_node
            vehicle_load[nodes.index(current_node)] -= vehicle_load[nodes.index(current_node)]
            cost_astar = 0
            vehicle_load = list(map(int, vehicle_load))
            dispatch = vehicle_load.copy()
            # variableIDS_list = []
            # always find closest post with parcels to pick/drop off.
            # start at closest node
            # get route and clear up any packages on this route

            while sum(vehicle_load) > 0:  # run until all parcels have been delivered
                post_idx = self.find_closest_post(vehicle_load, current_node, graph)  # idx of closest post with parcel demand
                target = nodes[post_idx]  # convert idx to node object

                vehicle_load[post_idx] -= vehicle_load[post_idx]  # take/drop all parcels
                route.append(target)

            #route_ordered = self.make_route_sequence(route)
            #graph.print_path(route_ordered)
            routes.append(route)

            # Extract 'latitude' and 'longitude' from station ID
            csv_file = config_parser.get_csv_path(use_case_graph)
            location_station_dict = CloUpdateHandler.extract_location_station_dict(csv_file)
            station_id = vehicles[i].start_node
            lat, lon = list(location_station_dict.keys())[list(location_station_dict.values()).index(station_id)]

            # Append route to the list. Also, "start_address" is necessary for each vehicle which we later use for TSP.
            converted_routes.append(
                {"UUID": vehicles[i].name,
                 "start_address": {
                     "lat": lat,
                     "lon": lon,
                     "location_id": station_id
                 },
                 "route": self.map_parcels_to_route(route, dispatch, graph, vehicles[i])})

        return converted_routes

    @staticmethod
    def map_parcels_to_route(route, loads, graph, vehicle):
        """Maps parcels UUIDs to the vehicle route: existing parcels on hte vehicles + additional parcels alocated
        loads_diff: position of addtional parcels to the vehicles routes from adhoc order"""
        nodes = graph.nodes
        converted_route = []
        parcel_list= vehicle.parcels
        parcel_list_pickup = parcel_list.copy()
        step_num = 1  # ittreation index for rank field

        if len(route) == 1 and loads[nodes.index(route[0])] == 0:
            return []

        # map parcel UUIDs to route
        for idx, node in enumerate(route):
            node_idx = None
            for i, n in enumerate(nodes):
                if n.id == node.id:
                    node_idx = i
                    break
            vehicle_parcels_unload = [x.uuid for x in parcel_list if x.target == node.id]
            vehicle_parcels_load = [x.uuid for x in parcel_list_pickup if x.current_location == node.id]

            if (int(loads[node_idx]) > 0 or idx == 0):
                converted_route.append({
                    "id": step_num,
                    "rank": step_num,
                    "complete": 0,
                    "due_time": None,
                    "load": vehicle_parcels_load,
                    "unload": vehicle_parcels_unload,
                    "location":{
                        "city": None,
                        "country": None,
                        "address": node.name,
                        "latitude":node.lat,
                        "longitude":node.lon,
                        "station":node.id,
                        "postal_code": None
                    },
                    "dependency": {
                        "plan": None,
                        "plan_step": None
                    }
                })
                step_num += 1

                for parcel in parcel_list[:]:  # removes the added parcels from the pending parcel lists for delivery and pickup
                    if parcel.uuid in vehicle_parcels_unload:
                        parcel_list.remove(parcel)
                for parcel in parcel_list_pickup[:]:
                    if parcel.uuid in vehicle_parcels_load:
                        parcel_list_pickup.remove(parcel)

            ##Adding the residual loading location for parcels pickup locations: vehicle_parcel_load == residual loading locaitons to be added
        for node in graph.nodes:
            vehicle_parcels_load = [x.uuid for x in parcel_list_pickup if x.current_location == node.id]
            if vehicle_parcels_load:
                converted_route.append({
                    "id": step_num,
                    "rank": step_num,
                    "complete": 0,
                    "due_time": None,
                    "load": vehicle_parcels_load,
                    "unload": [],
                    "location": {
                        "city": None,
                        "country": None,
                        "address": node.name,
                        "latitude": node.lat,
                        "longitude": node.lon,
                        "station": node.id,
                        "postal_code": None
                    },
                    "dependency": {
                        "plan": None,
                        "plan_step": None
                    }
                })
                step_num += 1

                for parcel in parcel_list_pickup[:]:
                    if parcel.uuid in vehicle_parcels_load:
                        parcel_list_pickup.remove(parcel)

            #check if all parcels mapped sucessfuly
        if len(parcel_list) > 0 or len(parcel_list_pickup) > 0:
            print("Parcels not mapped correctly on route")

        return converted_route

    @staticmethod
    def parse_vehicles(clos):
        """Create a list of Vehicle objects from JSON input"""
        vehicles = []
        for clo in clos:
            parcels = []
            # Go through parcels that are already on the vehicle
            # and only need to be delivered and not picked up as well.
            for parcel in clo["parcels"]:
                parcels.append(Parcel(parcel["UUIDParcel"], parcel["destination"],
                                      parcel["weight"], clo["currentLocation"], country=parcel["country"]))
            capacity = clo["capacity"] - len(parcels)
            vehicles.append(Vehicle(clo["UUID"], clo["currentLocation"], parcels, capacity, country=clo["country"]))
        return vehicles

    @staticmethod
    def parse_deliveries(evt_type, clos, requests, use_case):
        if use_case == SLO_CRO_USE_CASE:
            # Event "crossBorder" already has all parcels on the truck so no pickups are necessary. This means
            # that only deliveries_origin will be used for transportation
            deliveries_origin = []
            deliveries_diff = []
            # list of additional parcels from request
            if evt_type == "brokenVehicle":
                deliveries_diff = [Parcel(x["UUIDParcel"], x["destination"],
                                          x["weight"], x["pickup"],
                                          "order", country=x["country"]) for x in requests]
            elif evt_type == "dailyRequest" or "pickupRequest" or "crossBorder":
                deliveries_diff = [Parcel(x["UUIDParcel"], x["destination"],
                                          x["weight"], x["pickup"],
                                          "order", country=x["country"]) for x in requests]
            # list of parcels on CLOs before request
            for clo in clos:
                for parcel in clo["parcels"]:
                    deliveries_origin.append(Parcel(parcel["UUIDParcel"], parcel["destination"],
                                                    parcel["weight"], clo["currentLocation"], country=clo["country"]))
            deliveries = Deliveries(deliveries_origin, deliveries_diff)

            return deliveries

        if use_case == ELTA_USE_CASE:
            deliveries_origin = []
            # list of additional parcels from request
            if evt_type == "brokenVehicle":
                deliveries_diff = [Parcel(x["UUIDParcel"], x["destination"],
                                          x["weight"], x["pickup"], "order") for x in requests]
            else:
                deliveries_diff = [Parcel(x["UUIDParcel"], x["destination"],
                                          x["weight"], x["pickup"], "order") for x in requests]
            # list of parcels on CLOs before request
            for clo in clos:
                for parcel in clo["parcels"]:
                    deliveries_origin.append(Parcel(parcel["UUIDParcel"], parcel["destination"],
                                                    parcel["weight"], clo["currentLocation"], country=parcel["country"]))
            deliveries = Deliveries(deliveries_origin, deliveries_diff)

            return deliveries

    ####################################################################################
    # Helper methods and methods used for specific use case or purpose
    ####################################################################################

    def map_slo_cro_vehicles(self, vehicles, event_type):
        """
        Map vehicles to first or second graph. First graph represents SLO nodes and the second
        graphs represents CRO nodes.
        :param vehicles:
        :return:
        """
        map_v = [[], []]

        # First graph is SLO, second graph is CRO
        for v in vehicles:
            if SLOVENIA == v.country:
                # map SLO parcels to border nodes if necessary
                v.parcels = self.map_slo_cro_deliveries(v.parcels, event_type)[0]
                map_v[0].append(v)
            elif CROATIA == v.country:
                # map CRO parcels to border nodes if necessary
                v.parcels = self.map_slo_cro_deliveries(v.parcels, event_type)[1]
                map_v[1].append(v)
            else:
                print("Vehicle start node does not have 'S' or 'H'.")
                exit(1)

        return map_v

    def map_slo_cro_deliveries(self, deliveries, event_type):
        """
        Map deliveries for SLO-CRO use case. For each parcel, we check current (start) location
        and destination (target). If parcel needs to be delivered from SLO to CRO, we will
        assign the closest border node as target, if CRO node assigned that is not the border node.
        :param deliveries:
        :return:
        """
        delivery_parts = [[],[]] # First one is for SLO nodes, Second one is for CRO nodes
        for parcel in deliveries:
            if "SLO" == parcel.country: # Source country
                #if parcel.("CRO") or parcel.target.startswith("HP"):
                if parcel.target.startswith("CRO") or parcel.target.startswith("HP"):
                    # assign closest cro border node
                    cro_border_nodes = config_parser.get_border_nodes_cro()
                    if event_type == "crossBorder":
                        cro_border_nodes = config_parser.get_border_nodes_cro_cross_border()
                    if parcel.target not in cro_border_nodes:
                        # TODO: assign the closest node instead of the first one
                        parcel.target = cro_border_nodes[0]
                delivery_parts[0].append(parcel)
            elif CROATIA == parcel.country: # Source country
                if parcel.target.startswith("SLO") or parcel.target.startswith("PS"):
                    # assign closest slo border node
                    slo_border_nodes = config_parser.get_border_nodes_slo()
                    if event_type == "crossBorder":
                        slo_border_nodes = config_parser.get_border_nodes_slo_cross_border()
                    if parcel.target not in slo_border_nodes:
                        # TODO: assign the closest node instead of the first one
                        parcel.target = slo_border_nodes[0]
                delivery_parts[1].append(parcel)
            else:
                print("Current parcel country is not 'SLO' nor 'CRO'! Data: ",
                      parcel.uuid, ", target: ", parcel.target, ", location now:", parcel.current_location,
                      ", type: ", parcel.type, ", country: ", parcel.country)
                exit(1)

        return delivery_parts
