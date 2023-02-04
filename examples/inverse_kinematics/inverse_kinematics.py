import numpy as np
from casadi import vertcat, nlpsol, horzcat
import ezc3d
from pathlib import Path
from pyomeca import Markers

from bionc.bionc_casadi import (
    NaturalCoordinates,
    SegmentNaturalCoordinates,
)
from bionc.bionc_numpy import NaturalCoordinates as NaturalCoordinatesNumpy
from bionc import Viz, BiomechanicalModel

# models can only be loaded if a numpy model
# but not working yet with import, model_numpy.Q_from_markers ...
# model = BiomechanicalModelNumpy.load(Path.cwd().parent.absolute().__str__() + "/examples/models/lower_limb.nc")
# model_numpy = model
from tests.utils import TestUtils


def _solve_nlp(method, nlp, Q_init, lbg, ubg, options):
    S = nlpsol(
        "InverseKinematics",
        method,
        nlp,
        options,
    )
    r = S(x0=Q_init, lbg=lbg, ubg=ubg)
    return r


class InverseKinematics:
    def __init__(
        self,
        model: BiomechanicalModel,
        experimental_markers: np.ndarray | str,
    ):
        self.frame_per_frame = None
        self.Qopt = None
        self.model = model
        self.model_mx = model.to_mx()

        if isinstance(experimental_markers, str):
            self.experimental_markers = Markers.from_c3d(experimental_markers).to_numpy()
        elif isinstance(experimental_markers, np.ndarray):
            if (
                experimental_markers.shape[0] != 3
                or experimental_markers.shape[1] < 1
                or len(experimental_markers.shape) < 3
            ):
                raise ValueError("experimental_markers must be a 3xNxM numpy array")
            self.experimental_markers = experimental_markers
        else:
            raise ValueError("experimental_markers must be a numpy array or a path to a c3d file")

        self.Q_init = self.model.Q_from_markers(self.experimental_markers[:, :, :])
        self.nb_frames = self.experimental_markers.shape[2]
        self.nb_markers = self.experimental_markers.shape[1]

    def solve(
        self,
        method: str = "ipopt",
        frame_per_frame: bool = True,
    ):

        if method == "sqpmethod":
            options = {
                "beta": 0.8,
                "c1": 0.0001,
                "hessian_approximation": "exact",
                "lbfgs_memory": 10,
                "max_iter": 50,
                "max_iter_ls": 3,
                "merit_memory": 4,
                "print_header": True,
                "print_time": True,
                "qpsol": "qpoases",
                "tol_du": 0.1,
                "tol_pr": 0.1,
                "qpsol_options": {"error_on_fail": False},
            }
        elif method == "ipopt":
            options = {}
        else:
            raise ValueError("method must be 'sqpmethod' or 'ipopt'")

        self.frame_per_frame = frame_per_frame
        Q, vert_Q = self._declare_sym_Q()

        if frame_per_frame:
            Qopt = np.zeros((12 * self.model.nb_segments, self.nb_frames))
            lbg = np.zeros(self.model.nb_holonomic_constraints)
            ubg = np.zeros(self.model.nb_holonomic_constraints)
            constraints = self._constraints(Q)
            print(constraints)
            for f in range(self.nb_frames):
                objective = self._objective(Q, self.experimental_markers[:, :, f: f + 1])
                nlp = dict(
                        x=vert_Q,
                        f=objective,
                        g=constraints,
                    )
                Q_init = self.Q_init[:, f : f + 1]
                bionc_viz = Viz(
                    self.model,
                    show_center_of_mass=False,  # no center of mass in this example
                    show_xp_markers=True,
                    show_model_markers=True,
                )
                bionc_viz.animate(NaturalCoordinatesNumpy(Q_init), markers_xp=self.experimental_markers[:, :, f: f + 1])
                r = _solve_nlp(method, nlp, Q_init, lbg, ubg, options)
                Qopt[:, f : f + 1] = r["x"].toarray()
        else:
            constraints = self._constraints(Q)
            objective = self._objective(Q, self.experimental_markers)
            nlp = dict(
                x=vert_Q,
                f=objective,
                g=constraints,
            )
            Q_init = self.Q_init.reshape((12 * self.model.nb_segments * self.nb_frames, 1))
            lbg = np.zeros(self.model.nb_holonomic_constraints * self.nb_frames)
            ubg = np.zeros(self.model.nb_holonomic_constraints * self.nb_frames)
            r = _solve_nlp(method, nlp, Q_init, lbg, ubg, options)
            Qopt = r["x"].toarray()

        self.Qopt = Qopt.reshape((12 * self.model.nb_segments, self.nb_frames))

        return Qopt

    def _declare_sym_Q(self):
        Q_sym = []
        nb_frames = 1 if self.frame_per_frame else self.nb_frames
        for f in range(nb_frames):
            Q_f_sym = []
            for ii in range(self.model.nb_segments):
                Q_f_sym.append(SegmentNaturalCoordinates.sym(f"_{ii}_{f}"))
            Q_sym.append(vertcat(*Q_f_sym))
        Q = horzcat(*Q_sym)
        vert_Q = vertcat(*Q_sym)
        return Q, vert_Q

    def _objective(self, Q, experimental_markers):
        error_m = 0
        nb_frames = 1 if self.frame_per_frame else self.nb_frames
        for f in range(nb_frames):
            Q_f = NaturalCoordinates(Q[:, f])
            phim = self.model_mx.markers_constraints(experimental_markers[:3, :, f], Q_f, only_technical=True)
            error_m += 1 / 2 * phim.T @ phim
        return error_m

    def _constraints(self, Q):
        nb_frames = 1 if self.frame_per_frame else self.nb_frames
        phir = []
        phik = []
        for f in range(nb_frames):
            Q_f = NaturalCoordinates(Q[:, f])
            phir.append(self.model_mx.rigid_body_constraints(Q_f))
            phik.append(self.model_mx.joint_constraints(Q_f))
        return vertcat(*phir, *phik)

    def animate(self):
        bionc_viz = Viz(
            self.model,
            show_center_of_mass=False,  # no center of mass in this example
            show_xp_markers=True,
            show_model_markers=True,
        )
        bionc_viz.animate(NaturalCoordinatesNumpy(self.Qopt), markers_xp=self.experimental_markers)


def main():
    bionc = TestUtils.bionc_folder()
    module = TestUtils.load_module(bionc + "/examples/model_creation/main.py")

    optimizer = "ipopt"
    # optimizer = "sqpmethod"

    # Generate c3d file
    filename = module.generate_c3d_file()
    # Generate model
    model = module.model_creation_from_measured_data(filename)
    model_numpy = model

    markers = Markers.from_c3d(filename).to_numpy()[:3, :, :]
    # markers = np.repeat(markers, 20, axis=2)
    markers = markers[:, :, 0:1]
    ik_solver = InverseKinematics(model_numpy, markers)
    Qopt = ik_solver.solve(method=optimizer, frame_per_frame=True)
    print(Qopt)
    # ik_solver.animate()
    bionc_viz = Viz(
        model_numpy,
        show_center_of_mass=False,  # no center of mass in this example
        show_xp_markers=True,
        show_model_markers=True,
    )
    bionc_viz.animate(NaturalCoordinatesNumpy(Qopt), markers_xp=markers[:3, :, 0:1])

if __name__ == "__main__":
    main()