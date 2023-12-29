from .base import *
from .extru_square_bracket import SquareBracket40_4302

parts = {
    "alu4040tube": lambda: Extru40_4040(height=100).get_part(),
    "4302Bracket": lambda: SquareBracket40_4302().get_part(),
}
