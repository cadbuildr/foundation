from cadbuildr.foundation.operations.extrude import Extrusion, Hole
from cadbuildr.foundation.operations.lathe import Lathe
from cadbuildr.foundation.operations.fillet import Fillet
from cadbuildr.foundation.operations.chamfer import Chamfer
from cadbuildr.foundation.operations.loft import Loft
from cadbuildr.foundation.operations.sweep import Sweep
from typing import Union

operation_types_tuple = (Extrusion, Hole, Lathe, Fillet, Chamfer, Loft, Sweep)

OperationTypes = Union[Extrusion, Hole, Lathe, Fillet, Chamfer, Loft, Sweep]
