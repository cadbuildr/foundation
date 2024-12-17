from cadbuildr.foundation import *


class GridXY:
    """Useful wrapper around a class that has a .get_assy method to generate a grid of them"""

    def __init__(
        self, assy_factory, n_x: int, n_y: int, spacing_x: float, spacing_y: float
    ):
        self.assy_factory = assy_factory
        self.n_x = n_x
        self.n_y = n_y
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y

    def get_assy(self) -> Assembly:
        self.assembly = Assembly()
        for i in range(self.n_x):
            for j in range(self.n_y):
                tf_helper = TFHelper()
                tf_helper.translate_x(i * self.spacing_x)
                tf_helper.translate_y(j * self.spacing_y)
                self.assembly.add_component(
                    self.assy_factory.get_assy(), tf_helper.get_tf()
                )
        return self.assembly
