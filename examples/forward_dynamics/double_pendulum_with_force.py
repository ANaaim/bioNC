import numpy as np

from bionc import NaturalAxis, CartesianAxis, RK4, TransformationMatrixType
from bionc.bionc_numpy import (
    BiomechanicalModel,
    NaturalSegment,
    JointType,
    SegmentNaturalCoordinates,
    NaturalCoordinates,
    SegmentNaturalVelocities,
    NaturalVelocities,
    ExternalForceSet,
)


def build_n_link_pendulum(nb_segments: int = 1) -> BiomechanicalModel:
    """Build a n-link pendulum model"""
    if nb_segments < 1:
        raise ValueError("The number of segment must be greater than 1")
    # Let's create a model
    model = BiomechanicalModel()
    # number of segments
    # fill the biomechanical model with the segment
    for i in range(nb_segments):
        name = f"pendulum_{i}"
        model[name] = NaturalSegment.with_cartesian_inertial_parameters(
            name=name,
            alpha=np.pi / 2,  # setting alpha, beta, gamma to pi/2 creates a orthogonal coordinate system
            beta=np.pi / 2,
            gamma=np.pi / 2,
            length=1,
            mass=1,
            center_of_mass=np.array([0, -0.5, 0]),  # in segment coordinates system
            inertia=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),  # in segment coordinates system
            inertial_transformation_matrix=TransformationMatrixType.Buv,
        )
    # add a revolute joint (still experimental)
    # if you want to add a revolute joint,
    # you need to ensure that x is always orthogonal to u and v
    model._add_joint(
        dict(
            name="hinge_0",
            joint_type=JointType.GROUND_REVOLUTE,
            parent="GROUND",
            child="pendulum_0",
            parent_axis=[CartesianAxis.X, CartesianAxis.X],
            child_axis=[NaturalAxis.V, NaturalAxis.W],  # meaning we pivot around the cartesian x-axis
            theta=[np.pi / 2, np.pi / 2],
        )
    )
    for i in range(1, nb_segments):
        model._add_joint(
            dict(
                name=f"hinge_{i}",
                joint_type=JointType.REVOLUTE,
                parent=f"pendulum_{i - 1}",
                child=f"pendulum_{i}",
                parent_axis=[NaturalAxis.U, NaturalAxis.U],
                child_axis=[NaturalAxis.V, NaturalAxis.W],
                theta=[np.pi / 2, np.pi / 2],
            )
        )
    return model

    model.save("pendulum_with_force.nmod")

    return model


def apply_force_and_drop_pendulum(t_final: float = 10, external_forces: ExternalForceSet = None, nb_segments: int = 1):
    """
    This function is used to test the external force

    Parameters
    ----------
    t_final: float
        The final time of the simulation
    external_forces: ExternalForceSet
        The external forces applied to the model
    nb_segments: int
        The number of segments of the model

    Returns
    -------
    tuple[BiomechanicalModel, np.ndarray, np.ndarray, Callable]:
        model : BiomechanicalModel
            The model to be simulated
        time_steps : np.ndarray
            The time steps of the simulation
        all_states : np.ndarray
            The states of the system at each time step X = [Q, Qdot]
        dynamics : Callable
            The dynamics of the system, f(t, X) = [Xdot, lambdas]

    """
    model = build_n_link_pendulum(nb_segments=nb_segments)

    tuple_of_Q = [
        SegmentNaturalCoordinates.from_components(u=[1, 0, 0], rp=[0, -i, 0], rd=[0, -i - 1, 0], w=[0, 0, 1])
        for i in range(0, nb_segments)
    ]
    Q = NaturalCoordinates.from_qi(tuple(tuple_of_Q))

    tuple_of_Qdot = [
        SegmentNaturalVelocities.from_components(udot=[0, 0, 0], rpdot=[0, 0, 0], rddot=[0, 0, 0], wdot=[0, 0, 0])
        for i in range(0, nb_segments)
    ]
    Qdot = NaturalVelocities.from_qdoti(tuple(tuple_of_Qdot))

    time_steps, all_states, dynamics = drop_the_pendulum(
        model=model,
        Q_init=Q,
        Qdot_init=Qdot,
        external_forces=external_forces,
        t_final=t_final,
        steps_per_second=60,
    )

    return model, time_steps, all_states, dynamics


def drop_the_pendulum(
    model: BiomechanicalModel,
    Q_init: NaturalCoordinates,
    Qdot_init: NaturalVelocities,
    external_forces: ExternalForceSet,
    t_final: float = 2,
    steps_per_second: int = 50,
):
    """
    This function simulates the dynamics of a natural segment falling from 0m during 2s

    Parameters
    ----------
    model : BiomechanicalModel
        The model to be simulated
    Q_init : SegmentNaturalCoordinates
        The initial natural coordinates of the segment
    Qdot_init : SegmentNaturalVelocities
        The initial natural velocities of the segment
    external_forces : ExternalForceSet
        The external forces applied to the model
    t_final : float, optional
        The final time of the simulation, by default 2
    steps_per_second : int, optional
        The number of steps per second, by default 50

    Returns
    -------
    tuple:
        time_steps : np.ndarray
            The time steps of the simulation
        all_states : np.ndarray
            The states of the system at each time step X = [Q, Qdot]
        dynamics : Callable
            The dynamics of the system, f(t, X) = [Xdot, lambdas]
    """

    print("Evaluate Rigid Body Constraints:")
    print(model.rigid_body_constraints(Q_init))
    print("Evaluate Rigid Body Constraints Jacobian Derivative:")
    print(model.rigid_body_constraint_jacobian_derivative(Qdot_init))

    if (model.rigid_body_constraints(Q_init) > 1e-6).any():
        print(model.rigid_body_constraints(Q_init))
        raise ValueError(
            "The segment natural coordinates don't satisfy the rigid body constraint, at initial conditions."
        )

    t_final = t_final  # [s]
    steps_per_second = steps_per_second
    time_steps = np.linspace(0, t_final, steps_per_second * t_final + 1)

    # initial conditions, x0 = [Qi, Qidot]
    states_0 = np.concatenate((Q_init.to_array(), Qdot_init.to_array()), axis=0)

    fext = external_forces

    # Create the forward dynamics function Callable (f(t, x) -> xdot)
    def dynamics(t, states):
        idx_coordinates = slice(0, model.nb_Q)
        idx_velocities = slice(model.nb_Q, model.nb_Q + model.nb_Qdot)

        qddot, lambdas = model.forward_dynamics(
            NaturalCoordinates(states[idx_coordinates]),
            NaturalVelocities(states[idx_velocities]),
            external_forces=fext,
        )
        return np.concatenate((states[idx_velocities], qddot.to_array()), axis=0), lambdas

    # Solve the Initial Value Problem (IVP) for each time step
    normalize_idx = model.normalized_coordinates
    all_states = RK4(t=time_steps, f=lambda t, states: dynamics(t, states)[0], y0=states_0, normalize_idx=normalize_idx)

    return time_steps, all_states, dynamics


def main(mode: str = "force_equilibrium"):
    nb_segments = 2
    # add an external force applied on the segment 0
    # first build the object
    fext = ExternalForceSet.empty_from_nb_segment(nb_segment=nb_segments)
    # then add a force
    if mode == "force_equilibrium":
        wrench = np.concatenate((np.array([0, 0, 0]), np.array([0, 0, 1 * 9.81])))
        fext.add_in_global_local_point(segment_index=0, external_force=wrench, point_in_local=np.array([0, 0.5, 0]))
        wrench2 = np.concatenate((np.array([0, 0, 0]), np.array([0, 0, 1 * 9.81])))
        fext.add_in_global_local_point(segment_index=1, external_force=wrench2, point_in_local=np.array([0, 0.5, 0]))

    elif mode == "no_equilibrium":
        wrench1 = np.concatenate((np.array([0, 0, 0]), np.array([0, 0, 1 * 9.81])))
        fext.add_in_global_local_point(segment_index=0, external_force=wrench1, point_in_local=np.array([0, 0.25, 0]))
        fext.add_in_global_local_point(segment_index=1, external_force=wrench1, point_in_local=np.array([0, 0.25, 0]))
    else:
        raise ValueError("mode must be 'force_equilibrium', 'moment_equilibrium' or 'no_equilibrium'")

    model, time_steps, all_states, dynamics = apply_force_and_drop_pendulum(
        t_final=10, external_forces=fext, nb_segments=nb_segments
    )

    return model, all_states, time_steps


if __name__ == "__main__":
    # model, all_states = main(mode="force_equilibrium")
    model, all_states, time_steps = main(mode="no_equilibrium")

    # animate the motion
    from pyorerun import PhaseRerun
    from bionc.vizualization.pyorerun_interface import BioncModelNoMesh

    prr = PhaseRerun(t_span=time_steps)
    model_interface = BioncModelNoMesh(model)
    prr.add_animated_model(model_interface, all_states[:24, :])
    prr.rerun()
