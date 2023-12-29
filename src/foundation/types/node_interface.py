class NodeInterface:
    """A node interface is a group of node that shares similar "type". For instance a plane can be defined using multiple parents
    In implementing such a node, we use double ( or more ) inheritance of that node from the Node class ( or inherited) as well as
    a Nodeinterface ( or inherited). An interface can contain methods that can be shared among the different child class. For instance a
    rendering function for a plane will be shared among all the plane nodes."""

    is_interface = True

    def __init__(self):
        pass

    @classmethod
    def get_interface_types(cls):
        """From the class that the Node inherit from, we only select the ones that are NodeInterface (see class definition)"""
        types = []
        for o in cls.mro():
            try:
                if o.is_interface:
                    types.append(o.__name__)
            except AttributeError:
                pass
        return types
