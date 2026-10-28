"""Constructed continuum consistency checks; NumPy required."""
import numpy as np


def main():
    identity = np.eye(3)
    shear = np.array([[1.0, 0.7, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    green = (shear.T @ shear - identity) / 2.0
    for theta in np.linspace(0.0, np.pi, 31):
        c, s = np.cos(theta), np.sin(theta)
        q = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        f = q @ shear
        assert np.allclose((f.T @ f - identity) / 2.0, green)
        assert abs(np.linalg.det(f) - 1.0) < 1e-12
    rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    h = rotation - identity
    assert np.allclose(h + h.T + h.T @ h, 0.0)
    assert np.linalg.norm((h + h.T) / 2.0) > 1.0
    f = np.diag([1.2, 0.9, 1.1])
    sigma = np.array([[6.0, 2.0, 0.0], [2.0, 3.0, 0.0], [0.0, 0.0, 1.0]])
    normal = np.array([1.0, 2.0, 3.0]) / np.sqrt(14.0)
    jacobian = np.linalg.det(f)
    piola = jacobian * sigma @ np.linalg.inv(f).T
    area = jacobian * np.linalg.inv(f).T @ normal
    assert np.allclose(sigma @ area, piola @ normal)
    drive, height, viscosity = 5000.0, 0.002, 1.0
    y = np.linspace(0.0, height, 10001)
    velocity = drive * y * (2.0 * height - y) / (2.0 * viscosity)
    derivative = drive * (height - y) / viscosity
    flux = np.trapezoid(velocity, y)
    dissipation = np.trapezoid(viscosity * derivative**2, y)
    assert abs(drive * flux - dissipation) < 1e-8
    print('PASS: 31 rotation-invariant finite-strain states')
    print('PASS: finite rotation exposes small-strain approximation boundary')
    print('PASS: reference/current force conversion on an oblique face')
    print('PASS: falling-film flux and gravity/viscous power closure')


if __name__ == '__main__':
    main()
