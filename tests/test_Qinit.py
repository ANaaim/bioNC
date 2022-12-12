import os
import numpy as np
import pytest

from .utils import TestUtils
from pyomeca import Markers


@pytest.mark.parametrize(
    "bionc_type",
    [
        "numpy",
        "casadi",
    ],
)
def test_biomech_model(bionc_type):
    bionc = TestUtils.bionc_folder()
    module = TestUtils.load_module(bionc + "/examples/model_creation/main.py")

    # Generate c3d file
    filename = module.generate_c3d_file()
    # Generate model
    model = module.model_creation_from_measured_data(filename)

    markers = Markers.from_c3d(filename).to_numpy()

    # delete c3d file
    os.remove(filename)

    Q1 = model.Q_from_markers(markers[:, :, 0:1])
    Q2 = model.Q_from_markers(markers[:, :, 1:2])

    with pytest.raises(
        ValueError,
        # match="markers should have 11 columns, and should include the following markers: "
        #       "['RFWT', 'LFWT', 'RBWT', 'LBWT', 'RKNI', 'RKNE', 'RANE', 'RANI', 'RHEE', 'RTARI', 'RTAR']"
    ):
        model.Q_from_markers(markers[:, 0:2, 0:1])

    # Test Q
    TestUtils.assert_equal(
        Q1,
        np.array(
            [
                [-1.97643735e-01],
                [-1.40681863e-02],
                [-2.76666582e-02],
                [3.82151827e-01],
                [1.23308080e00],
                [9.43431586e-01],
                [2.52664189e-01],
                [1.30339712e00],
                [8.45309613e-01],
                [-4.97971346e-04],
                [1.66834832e-01],
                [1.78395812e-03],
                [7.42392213e-01],
                [-1.35030363e00],
                [-7.57773695e-01],
                [2.52664189e-01],
                [1.30339712e00],
                [8.45309613e-01],
                [2.89301813e-01],
                [1.34879082e00],
                [4.53159243e-01],
                [-9.26494598e-04],
                [-1.04713559e-01],
                [-4.55793738e-02],
                [-1.24156750e00],
                [-1.06108517e00],
                [-5.55215694e-01],
                [2.89301813e-01],
                [1.34879082e00],
                [4.53159243e-01],
                [3.41539338e-01],
                [1.39898950e00],
                [1.07256945e-01],
                [-2.90011466e-02],
                [-9.27954912e-02],
                [9.00491327e-03],
                [6.09833199e-01],
                [-1.59201264e00],
                [1.32810468e-01],
                [3.41539338e-01],
                [1.39898950e00],
                [1.07256945e-01],
                [2.29733087e-01],
                [1.43079340e00],
                [3.15796109e-02],
                [7.84488022e-03],
                [1.21605396e-01],
                [1.61456130e-03],
            ]
        ),
    )

    TestUtils.assert_equal(
        Q2,
        np.array(
            [
                [-1.97517298e-01],
                [-1.31603479e-02],
                [-2.55489647e-02],
                [3.96191359e-01],
                [1.23630732e00],
                [9.43076342e-01],
                [2.66311198e-01],
                [1.30696092e00],
                [8.45995743e-01],
                [1.29992544e-04],
                [1.66838042e-01],
                [1.03640520e-03],
                [7.29954588e-01],
                [-1.34764902e00],
                [-7.69844820e-01],
                [2.66311198e-01],
                [1.30696092e00],
                [8.45995743e-01],
                [2.98088655e-01],
                [1.34961945e00],
                [4.53051075e-01],
                [-8.37415457e-04],
                [-1.04076743e-01],
                [-4.46533859e-02],
                [-1.25552810e00],
                [-1.07354453e00],
                [-5.37267130e-01],
                [2.98088655e-01],
                [1.34961945e00],
                [4.53051075e-01],
                [3.42664570e-01],
                [1.39847636e00],
                [1.06435806e-01],
                [-2.79366374e-02],
                [-9.41925049e-02],
                [8.82789493e-03],
                [6.10046665e-01],
                [-1.59045662e00],
                [1.29116487e-01],
                [3.42664570e-01],
                [1.39847636e00],
                [1.06435806e-01],
                [2.29804464e-01],
                [1.43074578e00],
                [3.18061858e-02],
                [7.83143938e-03],
                [1.21347308e-01],
                [1.53455138e-03],
            ]
        ),
    )
