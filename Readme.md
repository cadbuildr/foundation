# Foundation Python lib

Foundation is a python library meant to be used as an API for creating 3D objects. Files using this library can be converted to DAG (Directed Acyclic Graph) files which can then be compiled for CAD, analysis, or other purposes.

This is the backbone of [Cadbuildr](https://cadbuildr.com/). See the documentation [here](https://documentation.cadbuildr.com/)

## Installation

If you plan on contributing to this project, you can install ( after cloning ) the library by running the following command in the root directory of the project:

```bash
pip install -e .
```

## Running the tests

The tests are a good place to start to understand how the library works. You can run the tests by running the following command in the root directory of the project:

```bash
pytest
```

Moreover there is a folder examples/ in the tests folder which contains some examples of how to use the library for basic parts.

## Publishing to PyPI

Build :

```bash
poetry build
```

Publish :

```bash
poetry publish
```
