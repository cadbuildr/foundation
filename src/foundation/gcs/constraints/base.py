from foundation.types.node_interface import NodeInterface
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from foundation.gcs.geometry import Primitive


class FoundationConstraint(NodeInterface):
    """Abstract class : NodeInterface for a constraint. A constraint can be
    - a 2D constraint on sketches (same length, right angle...)
    - a 3D constraint to join two components/subassemblies (called Joints)"""

    pass


class FoundationConstraint2D(FoundationConstraint):
    """Abstract class : NodeInterface for a 2D constraint on sketches"""

    def __init__(self, primitives: List["Primitive"], params: List[float]):
        self.params = params
        self.primitives = primitives
        # TODO ? should we even record the primitives/params in Foundation ? or only in the solver ?


class FoundationJoints(FoundationConstraint):
    """Abstract class : NodeInterface for a 3D constraint to join two components/subassemblies"""

    def __init__(self):
        pass
