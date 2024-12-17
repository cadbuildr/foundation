from cadbuildr.foundation.types.node_interface import NodeInterface


class Operation(NodeInterface):
    def get_frame(self):
        raise NotImplementedError(
            "Operation.get_frame() not implemented for all operations"
        )

    def set_component_name(self, name):
        # this is difficult to get rid off
        # during the assembly operations need the name of the component
        # to store the mesh, but this breaks the no cycle rule
        # of the graph
        # Solution is probably to make sure operations that depend
        # on others are correctly set in the graph (ie by default
        # operation will have as a child the previous operation of the same
        # component : also not ideal for splitting computing in parallel)
        # and then keep mesh by node_id instead of component name
        # during build.
        self.params["part_name"] = name
