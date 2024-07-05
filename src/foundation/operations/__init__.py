from foundation.operations.extrude import Extrusion, Hole
from foundation.operations.lathe import Lathe
from foundation.operations.fillet import Fillet
from foundation.operations.chamfer import Chamfer
from foundation.operations.loft import Loft
from typing import Union

operation_types_tuple = (Extrusion, Hole, Lathe, Fillet, Chamfer, Loft)

OperationTypes = Union[Extrusion, Hole, Lathe, Fillet, Chamfer, Loft]
