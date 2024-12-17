from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.exceptions import InvalidParameterValueException

default_colors: dict = {
    "red": [1, 0, 0],
    "green": [0, 1, 0],
    "blue": [0, 0, 1],
    "yellow": [1, 1, 0],
    "cyan": [0, 1, 1],
    "magenta": [1, 0, 1],
    "black": [0, 0, 0],
    "white": [1, 1, 1],
    "grey": [0.5, 0.5, 0.5],
    "orange": [1, 0.5, 0],
    "purple": [0.5, 0, 0.5],
    "brown": [0.5, 0.25, 0],
    "pink": [1, 0.75, 0.8],
    "light_blue": [0.68, 0.85, 0.9],
    "light_green": [0.56, 0.93, 0.56],
    "dark_green": [0, 0.39, 0],
    "dark_grey": [0.25, 0.25, 0.25],
    "light_grey": [0.75, 0.75, 0.75],
    "dark_red": [0.5, 0, 0],
    "dark_blue": [0, 0, 0.5],
    "dark_yellow": [0.5, 0.5, 0],
    "dark_cyan": [0, 0.5, 0.5],
    "dark_magenta": [0.5, 0, 0.5],
    "dark_orange": [1, 0.5, 0],
    "dark_purple": [0.5, 0, 0.5],
    "dark_brown": [0.25, 0.12, 0],
    "dark_pink": [1, 0.75, 0.8],
    "beige": [0.96, 0.96, 0.86],
    "plywood": [0.73, 0.54, 0.38],
}


class MaterialChildren(NodeChildren):
    options: dict


class Material(Node):
    # counter for material names
    children_class = MaterialChildren

    def __init__(self):
        """Material Node"""
        super().__init__()
        self.name = "Material_{}".format(self.id)
        self.params = {"name": self.name}
        self.params["painted_node_ids"] = []

    def set_diffuse_colorRGB(self, r: int, g: int, b: int):
        if r > 255 or g > 255 or b > 255 or r < 0 or g < 0 or b < 0:
            raise InvalidParameterValueException(
                "r,g,b", (r, g, b), "between 0 and 255"
            )
        self.diffuse_color = (r, g, b)
        self.params["options"] = {"diffuse_color": self.diffuse_color}

    def set_transparency(self, alpha: float):
        if alpha > 1 or alpha < 0:
            raise InvalidParameterValueException("alpha", alpha, "between 0 and 1")
        self.params["options"] = {"alpha": alpha}

    def set_diffuse_color(self, color_name: str):
        if color_name not in default_colors:
            raise InvalidParameterValueException(
                "color_name", color_name, "one of {}".format(default_colors.keys())
            )
        self.diffuse_color = default_colors[color_name]
        self.params["options"] = {"diffuse_color": self.diffuse_color}
        # dict{str: dict{str: list[float]}}

    def attach_to_node(self, node_id):
        self.params["painted_node_ids"].append(node_id)


# MaterialChildren.__annotations__ = Dict[str, Any]
