from foundation.utils import has_cycle


# Unit tests
def test_has_cycle():
    # Test case 1: Simple acyclic graph
    graph1 = {1: {"deps": {"child": 2}}, 2: {"deps": {"child": 3}}, 3: {"deps": {}}}
    assert not has_cycle(graph1), "Test case 1 failed"

    # Test case 2: Simple cyclic graph
    graph2 = {
        1: {"deps": {"child": 2}},
        2: {"deps": {"child": 3}},
        3: {"deps": {"child": 1}},
    }
    assert has_cycle(graph2), "Test case 2 failed"

    # Test case 3: Acyclic graph with multiple children
    graph3 = {
        1: {"deps": {"child1": 2, "child2": 3}},
        2: {"deps": {}},
        3: {"deps": {"child": 4}},
        4: {"deps": {}},
    }
    assert not has_cycle(graph3), "Test case 3 failed"

    # Test case 4: Cyclic graph with multiple children
    graph4 = {
        1: {"deps": {"child1": 2, "child2": 3}},
        2: {"deps": {}},
        3: {"deps": {"child": 4}},
        4: {"deps": {"child": 1}},
    }
    assert has_cycle(graph4), "Test case 4 failed"
