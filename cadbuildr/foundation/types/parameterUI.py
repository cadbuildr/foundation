"""ParameterUI class

Example input dict
parameters = {
    "n_length":{"values":range(1,10), "default":4},
    "n_width":{"values":range(1,10), "default":2},
    "short_height":{"values":[True, False], "default":False},
}
"""


class ParameterUI:
    def __init__(self, params: dict):
        self.params = params
        self.check_input()

    def check_input(self):
        """Check that the dict of parameters is valid"""
        pass

    def to_dict(self):
        """Return a dict of the parameters"""
        return self.params

    def defaults(self):
        """Return a dict of the default parameters"""
        return {k: v["default"] for k, v in self.params.items()}
