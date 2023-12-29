#%%
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np


def node_label(key, value):
    return f"{key} : {value['type']}"


class NetworkXCompiler:
    def __init__(self, assy_graph):
        """assy_graph is a recursive dictionary with {id: child}"""
        self.assy_id = assy_graph[0]
        self.assy_graph = assy_graph[1]

    @staticmethod
    def _rec_build_graph(G, head_node_key, head_node):
        """Recursive function to build a graph from a node"""
        G.add_node(node_label(head_node_key, head_node))
        if "deps" not in head_node:
            return
        for child_key, child in head_node["deps"].items():
            NetworkXCompiler._rec_build_graph(G, child_key, child)
            G.add_edge(
                node_label(head_node_key, head_node), node_label(child_key, child)
            )

    def get_graph(self):
        G = nx.DiGraph()
        NetworkXCompiler._rec_build_graph(G, "head", self.assy_graph)

        nx.draw_networkx(G)
        plt.title("Graph of component")

        plt.show()
