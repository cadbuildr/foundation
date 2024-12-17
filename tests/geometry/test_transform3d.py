# %%
import numpy as np
from cadbuildr.foundation.geometry.transform3d import RotationMatrix, TransformMatrix

# only as a dependecy for tests
from pytransform3d.transformations import pq_from_transform


def test_from_eulerx():
    # 90 deg on x axis
    euler = np.array([np.pi / 2, 0, 0])
    rot = RotationMatrix.from_euler_angles(euler)
    assert np.allclose(rot.matrix, np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]))
    back_to_euler = rot.to_euler_angles()

    print(rot)
    print(back_to_euler)
    assert np.allclose(euler, back_to_euler)


def test_from_eulery():
    # 90 deg on y axis
    euler = np.array([0, np.pi / 2, 0])
    rot = RotationMatrix.from_euler_angles(euler)
    assert np.allclose(rot.matrix, np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]))
    back_to_euler = rot.to_euler_angles()

    print(rot)
    print(back_to_euler)
    assert np.allclose(euler, back_to_euler)


def test_from_eulerz():
    # 90 deg on z axis
    euler = np.array([0, 0, np.pi / 2])
    rot = RotationMatrix.from_euler_angles(euler)
    assert np.allclose(rot.matrix, np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]))
    back_to_euler = rot.to_euler_angles()

    print(rot)
    print(back_to_euler)
    assert np.allclose(euler, back_to_euler)


def test_from_quaternion_qo():
    quat = np.array([1, 0, 0, 0])
    rot = RotationMatrix.from_quaternion(quat)
    assert np.allclose(rot.matrix, np.eye(3, dtype="float"))
    back_to_quat = rot.to_quaternion()

    print(rot)
    print(back_to_quat)
    assert np.allclose(quat, back_to_quat)


def test_from_quaternion_05():
    quat = np.array([0.5, 0.5, 0.5, 0.5])
    # makes a 120 deg rotation around  i + j + k
    # which circulate dimensions along x,y,z

    rot = RotationMatrix.from_quaternion(quat)
    # TODO check the matrix
    back_to_quat = rot.to_quaternion()

    assert np.allclose(quat, back_to_quat)


def get_position_and_quaternions(transform):
    """return the position of the frame (from the parent frame)"""
    pq = pq_from_transform(transform)
    # position is first 3 value, quaternion is the last 4
    pos, quat = pq[:3], pq[3:]
    return pos, quat


def test_compare_to_pqtransform():
    eulers = np.array([0.1, 0.2, 0.3])

    rot = RotationMatrix.from_euler_angles(eulers)
    pos = np.array([1, 2, 3])

    transform = TransformMatrix.from_rotation_matrix_and_position(rot, pos)

    pos2, quat2 = get_position_and_quaternions(transform.matrix)
    pos1, quat1 = transform.to_position_quaternion()

    assert np.allclose(pos1, pos2)
    assert np.allclose(quat1, quat2)


def test_multiplication():
    """Test composition of 2 np.pi/2 rotations"""
    A = TransformMatrix.from_rotation_matrix_and_position(
        RotationMatrix.from_euler_angles([0, 0, np.pi / 2]), [0, 0, 0]
    )
    B = TransformMatrix.from_rotation_matrix_and_position(
        RotationMatrix.from_euler_angles([0, 0, np.pi / 2]), [0, 0, 0]
    )

    C = A.concat(B)

    assert np.allclose(C.get_position(), np.array([0, 0, 0]))

    C2 = TransformMatrix.from_rotation_matrix_and_position(
        RotationMatrix.from_euler_angles([0, 0, np.pi]), [0, 0, 0]
    )
    assert np.allclose(C.matrix, C2.matrix)


test_multiplication()
test_compare_to_pqtransform()
# %%
