from foundation.operations.extrude import Extrusion, Hole
from foundation.operations.lathe import Lathe
from foundation.operations.fillet import Fillet

OperationTypes = Extrusion | Hole | Lathe | Fillet
