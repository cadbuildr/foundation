from foundation.geometry import frame
import numpy as np
from foundation.geometry.tf_helper import get_rotation_matrix


def test_composability_of_translated_frames():
    f1 = frame.Frame.make_origin_frame()
    f2 = f1.get_translated_frame(name="1", translation=[0, 0, 1])
    f3 = f2.get_translated_frame(name="2", translation=[0, 0, 1])
    # print(f2.transform)
    # print(f3.transform)
    np.sum(f3.transform.matrix - f2.transform.matrix) == 1


def test_composability_of_rotated_frames():
    f1 = frame.Frame.make_origin_frame()
    x_axis = f1.get_x_axis()
    rot_mat = get_rotation_matrix(x_axis, np.pi)
    print(rot_mat)
    f2 = f1.get_rotated_frame(name="1", rot_mat=rot_mat)
    print(f2)
    f = f2
    for i in range(3):
        f = f.get_rotated_frame(name=f"r{i}", rot_mat=rot_mat)
    assert np.sum(f.transform.matrix - np.eye(4, dtype="float")) < 0.001


# TODO make much more tests including with components and assemblies to make sure the frames are correctly composed
