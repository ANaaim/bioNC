import numpy as np

from bionc import (
    BiomechanicalModel,
    SegmentNaturalCoordinates,
    SegmentNaturalVelocities,
    NaturalCoordinates,
    NaturalVelocities,
    NaturalSegment,
    JointType,
    EulerSequence,
    TransformationMatrixType,
    RK4,
)


def build_3d_pendulum():
    # Let's create a model
    model = BiomechanicalModel()
    # fill the biomechanical model with the segment
    model["pendulum"] = NaturalSegment.with_cartesian_inertial_parameters(
        name="pendulum",
        alpha=np.pi / 2,  # setting alpha, beta, gamma to pi/2 creates a orthogonal coordinate system
        beta=np.pi / 2,
        gamma=np.pi / 2,
        length=1,
        mass=1,
        center_of_mass=np.array([0, -1, -0.5]),  # in segment coordinates system
        inertia=np.array([[0.01, 0, 0], [0, 0.001, 0], [0, 0, 0.01]]),  # in segment coordinates system
    )
    # add a spherical joint (still experimental)

    model._add_joint(
        dict(
            name="spherical",
            joint_type=JointType.GROUND_SPHERICAL,
            parent="GROUND",
            child="pendulum",
            projection_basis=EulerSequence.XYZ,
            child_basis=TransformationMatrixType.Buv,
        )
    )

    model.save("pendulum_3d.nmod")

    return model


def apply_force_and_drop_pendulum(t_final: float = 10, joint_generalized_forces=None):
    """
    This function is used to test the external force

    Parameters
    ----------
    t_final: float
        The final time of the simulation
    joint_generalized_forces:

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
    model = build_3d_pendulum()

    Qi = SegmentNaturalCoordinates.from_components(u=[1, 0, 0], rp=[0, 0, 0], rd=[0, -1, 0], w=[0, 0, 1])
    Q = NaturalCoordinates(Qi)
    Qdoti = SegmentNaturalVelocities.from_components(udot=[0, 0, 0], rpdot=[0, 0, 0], rddot=[0, 0, 0], wdot=[0, 0, 0])
    Qdot = NaturalVelocities(Qdoti)

    time_steps, all_states, dynamics = drop_the_pendulum(
        model=model,
        Q_init=Q,
        Qdot_init=Qdot,
        joint_generalized_forces=joint_generalized_forces,
        t_final=t_final,
        steps_per_second=200,
    )

    return model, time_steps, all_states, dynamics


def drop_the_pendulum(
    model: BiomechanicalModel,
    Q_init: NaturalCoordinates,
    Qdot_init: NaturalVelocities,
    joint_generalized_forces=None,
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
    joint_generalized_forces : np.ndarray, optional
        The joint generalized forces, by default None
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

    # Create the forward dynamics function Callable (f(t, x) -> xdot)
    def dynamics(t, states):
        idx_coordinates = slice(0, model.nb_Q)
        idx_velocities = slice(model.nb_Q, model.nb_Q + model.nb_Qdot)

        qddot, lambdas = model.forward_dynamics(
            NaturalCoordinates(states[idx_coordinates]),
            NaturalVelocities(states[idx_velocities]),
            joint_generalized_forces=joint_generalized_forces,
            stabilization=dict(alpha=50, beta=20),
        )
        return np.concatenate((states[idx_velocities], qddot.to_array()), axis=0), lambdas

    # Solve the Initial Value Problem (IVP) for each time step
    # normalize_idx = model.normalized_coordinates
    all_states = RK4(
        t=time_steps,
        f=lambda t, states: dynamics(t, states)[0],
        y0=states_0,
        # normalize_idx=normalize_idx
    )

    return time_steps, all_states, dynamics


def post_computations(model: BiomechanicalModel, time_steps: np.ndarray, all_states: np.ndarray, dynamics):
    """
    This function computes:
     - the rigid body constraint error
     - the rigid body constraint jacobian derivative error
     - the joint constraint error
     - the lagrange multipliers of the rigid body constraint

    Parameters
    ----------
    model : NaturalSegment
        The segment to be simulated
    time_steps : np.ndarray
        The time steps of the simulation
    all_states : np.ndarray
        The states of the system at each time step X = [Q, Qdot]
    dynamics : Callable
        The dynamics of the system, f(t, X) = [Xdot, lambdas]

    Returns
    -------
    tuple:
        rigid_body_constraint_error : np.ndarray
            The rigid body constraint error at each time step
        rigid_body_constraint_jacobian_derivative_error : np.ndarray
            The rigid body constraint jacobian derivative error at each time step
        joint_constraints: np.ndarray
            The joint constraints at each time step
        lambdas : np.ndarray
            The lagrange multipliers of the rigid body constraint at each time step
    """
    idx_coordinates = slice(0, model.nb_Q)
    idx_velocities = slice(model.nb_Q, model.nb_Q + model.nb_Qdot)

    # compute the quantities of interest after the integration
    all_lambdas = np.zeros((model.nb_holonomic_constraints, len(time_steps)))
    defects = np.zeros((model.nb_rigid_body_constraints, len(time_steps)))
    defects_dot = np.zeros((model.nb_rigid_body_constraints, len(time_steps)))
    joint_defects = np.zeros((model.nb_joint_constraints, len(time_steps)))
    joint_defects_dot = np.zeros((model.nb_joint_constraints, len(time_steps)))

    for i in range(len(time_steps)):
        defects[:, i] = model.rigid_body_constraints(NaturalCoordinates(all_states[idx_coordinates, i]))
        defects_dot[:, i] = model.rigid_body_constraints_derivative(
            NaturalCoordinates(all_states[idx_coordinates, i]), NaturalVelocities(all_states[idx_velocities, i])
        )

        joint_defects[:, i] = model.joint_constraints(NaturalCoordinates(all_states[idx_coordinates, i]))
        # todo : to be implemented
        # joint_defects_dot = model.joint_constraints_derivative(
        #     NaturalCoordinates(all_states[idx_coordinates, i]),
        #     NaturalVelocities(all_states[idx_velocities, i]))
        # )

        all_lambdas[:, i : i + 1] = dynamics(time_steps[i], all_states[:, i])[1]

    return defects, defects_dot, joint_defects, all_lambdas


def main(show_results: bool = True):
    # as euler sequence is XYZ, we actuate along X axis first
    joint_generalized_forces = np.array([0.000, 0.0, 0.0])

    model, time_steps, all_states, dynamics = apply_force_and_drop_pendulum(
        t_final=5, joint_generalized_forces=joint_generalized_forces
    )

    if show_results:
        defects, defects_dot, joint_defects, all_lambdas = post_computations(
            model=model,
            time_steps=time_steps,
            all_states=all_states,
            dynamics=dynamics,
        )

        from viz import plot_series

        plot_series(time_steps, all_states[:12, :], legend="all_states")
        # Plot the results
        # the following graphs have to be near zero the more the simulation is long, the more constraints drift from zero
        plot_series(time_steps, defects, legend="rigid_constraint")  # Phi_r
        plot_series(time_steps, defects_dot, legend="rigid_constraint_derivative")  # Phi_r_dot
        plot_series(time_steps, joint_defects, legend="joint_constraint")  # Phi_j
        # the lagrange multipliers are the forces applied to maintain the system (rigidbody and joint constraints)
        plot_series(time_steps, all_lambdas, legend="lagrange_multipliers")  # lambda

    return model, all_states, time_steps


if __name__ == "__main__":
    model, all_states, time_steps = main(show_results=False)

    # animate the motion
    from pyorerun import PhaseRerun
    from bionc.vizualization.pyorerun_interface import BioncModelNoMesh

    prr = PhaseRerun(t_span=time_steps[:200])
    model_interface = BioncModelNoMesh(model)
    prr.add_animated_model(model_interface, all_states[:12, :200])
    prr.rerun()
    # This example stil have an unexpected behaviour, should at least fall in the direction of the gravity force during
    # the first frames, but it does not.
    # the pendulum should not rotate around the Z axis
