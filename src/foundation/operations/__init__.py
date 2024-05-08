from foundation.operations.extrude import Extrusion, Hole
from foundation.operations.lathe import Lathe
from foundation.operations.fillet import Fillet
from typing import Union

OperationTypes = Union[Extrusion, Hole, Lathe, Fillet]
