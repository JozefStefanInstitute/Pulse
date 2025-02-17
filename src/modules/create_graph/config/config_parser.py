import os
import json


class ConfigParser():

    def __init__(self, config_path='./modules/create_graph/config/config.json'):
        if not os.path.exists(config_path):
            print("File config.json does not exist. Config parser cannot be initialized!")
            exit(1)

        with open(config_path) as config:
            self.json_config = json.load(config)
        config.close()

    def get_pickle_path(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["slo_cro_pickle_path_crossborder"]
        if use_case == "SLO-CRO_urban":
            return self.json_config["slo_cro_pickle_path_urban"]
        elif use_case == "ELTA_urban1":
            return self.json_config["elta_pickle_path_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["elta_pickle_path_urban2"]


    def get_graph_path(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["slo_cro_json_graph_data_path_crossborder"]
        if use_case == "SLO-CRO_urban":
            return self.json_config["slo_cro_json_graph_data_path_urban"]
        elif use_case == "ELTA_urban1":
            return self.json_config["elta_json_graph_data_path_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["elta_json_graph_data_path_urban2"]
        else:
            print("Error - graph_path not defined.")

    def get_elta_path(self, use_case):
        if use_case == "ELTA_urban1":
            return self.json_config["elta_static_locations_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["elta_static_locations_urban2"]


    def get_csv_path(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["post_loc_slo_cro_crossborder"]
        elif use_case == "SLO-CRO_urban":
            return self.json_config["post_loc_slo_cro_urban"]
        elif use_case == "ELTA_urban1":
            return self.json_config["post_loc_elta_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["post_loc_elta_urban2"]
        else:
            print("Error - csv_path not defined.")

    def get_basic_map(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["map_basic_SLO-CRO_crossborder"]
        if use_case == "SLO-CRO_urban":
            return self.json_config["map_basic_SLO-CRO_urban"]
        elif use_case == "ELTA_urban1":
            return self.json_config["map_basic_ELTA_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["map_basic_ELTA_urban2"]
        else:
            print("Error - basic_map not defined.")

    def get_border_nodes_slo(self):
        return self.json_config["slo_border_nodes"]

    def get_border_nodes_cro(self):
         return self.json_config["cro_border_nodes"]

    def get_border_nodes_slo_cross_border(self):
        return self.json_config["slo_border_nodes_cross_border"]

    def get_border_nodes_cro_cross_border(self):
         return self.json_config["cro_border_nodes_cross_border"]

    def get_msb_few_url(self):
        return self.json_config["msb_fwd"]

    def get_eps(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["eps_slo_cro_crossborder"]
        elif use_case == "SLO-CRO_urban":
            return self.json_config["eps_slo_cro_urban"]
        elif use_case == "ELTA_urban1":
            return self.json_config["eps_elta_urban1"]
        elif use_case == "ELTA_urban2":
            return self.json_config["eps_elta_urban2"]

    def get_post_loc_type(self, use_case):
        if use_case == "SLO-CRO_crossborder":
            return self.json_config["post_loc_type_slo_cro"]
        elif use_case == "ELTA_urban1" or use_case == "ELTA_urban2":
            return self.json_config["post_loc_type_elta"]
        else:
            print("Error - post type not defined.")

    def get_graph_partitions(self):
        # Get the number of partitions used for graph split by partitioner
        return self.json_config["graph_partitions"]

    def get_logger_file(self):
        # Get the number of partitions used for graph split by partitioner
        return self.json_config["logger_file_location"]