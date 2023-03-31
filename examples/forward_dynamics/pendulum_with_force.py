import numpy as np

from bionc.bionc_numpy import (
    BiomechanicalModel,
    NaturalSegment,
    JointType,
    SegmentNaturalCoordinates,
    NaturalCoordinates,
    SegmentNaturalVelocities,
    NaturalVelocities,
    ExternalForceList,
    ExternalForce,
)
from bionc import NaturalAxis, CartesianAxis


def drop_the_pendulum(
    model: BiomechanicalModel,
    Q_init: NaturalCoordinates,
    Qdot_init: NaturalVelocities,
    external_forces: ExternalForceList,
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


def RK4(
    t: np.ndarray,
    f,
    y0: np.ndarray,
    normalize_idx: tuple[tuple[int, ...]] = None,
    args=(),
) -> np.ndarray:
    """
    Runge-Kutta 4th order method

    Parameters
    ----------
    t : array_like
        time steps
    f : Callable
        function to be integrated in the form f(t, y, *args)
    y0 : np.ndarray
        initial conditions of states
    normalize_idx : tuple(tuple)
        indices of states to be normalized together

    Returns
    -------
    y : array_like
        states for each time step

    """
    n = len(t)
    y = np.zeros((len(y0), n))
    y[:, 0] = y0
    for i in range(n - 1):
        h = t[i + 1] - t[i]
        yi = np.squeeze(y[:, i])
        k1 = f(t[i], yi, *args)
        k2 = f(t[i] + h / 2.0, yi + k1 * h / 2.0, *args)
        k3 = f(t[i] + h / 2.0, yi + k2 * h / 2.0, *args)
        k4 = f(t[i] + h, yi + k3 * h, *args)
        y[:, i + 1] = yi + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        if normalize_idx is not None:
            for idx in normalize_idx:
                y[idx, i + 1] = y[idx, i + 1] / np.linalg.norm(y[idx, i + 1])
    return y


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


if __name__ == "__main__":
    # Let's create a model
    model = BiomechanicalModel()
    # fill the biomechanical model with the segment
    model["pendulum"] = NaturalSegment(
        name="pendulum",
        alpha=np.pi / 2,  # setting alpha, beta, gamma to pi/2 creates a orthogonal coordinate system
        beta=np.pi / 2,
        gamma=np.pi / 2,
        length=1,
        mass=1,
        center_of_mass=np.array([0, -0.5, 0]),  # in segment coordinates system
        inertia=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),  # in segment coordinates system
    )
    # add a revolute joint (still experimental)
    # if you want to add a revolute joint,
    # you need to ensure that x is always orthogonal to u and v
    model._add_joint(
        dict(
            name="hinge",
            joint_type=JointType.GROUND_REVOLUTE,
            parent="GROUND",
            child="pendulum",
            parent_axis=[CartesianAxis.X, CartesianAxis.X],
            child_axis=[NaturalAxis.V, NaturalAxis.W],  # meaning we pivot around the cartesian x-axis
            theta=[np.pi / 2, np.pi / 2],
        )
    )

    model.save("pendulum_with_force.nmod")

    print(model.joints)
    print(model.nb_joints)
    print(model.nb_joint_constraints)

    Qi = SegmentNaturalCoordinates.from_components(u=[1, 0, 0], rp=[0, 0, 0], rd=[0, -1, 0], w=[0, 0, 1])
    Q = NaturalCoordinates(Qi)
    Qdoti = SegmentNaturalVelocities.from_components(udot=[0, 0, 0], rpdot=[0, 0, 0], rddot=[0, 0, 0], wdot=[0, 0, 0])
    Qdot = NaturalVelocities(Qdoti)

    print(model.joint_constraints(Q))
    print(model.joint_constraints_jacobian(Q))
    print(model.holonomic_constraints(Q))
    print(model.holonomic_constraints_jacobian(Q))

    # The actual simulation
    t_final = 10

    # add an external force applied on the segment 0
    fext = ExternalForceList.empty_from_nb_segment(1)
    force1 = ExternalForce.from_components(
        # force=np.array([0, 0, 1 * 9.81]),
        # # force=np.array([0, 0, 0]),
        # torque=np.array([0, 0, 0]),
        # application_point_in_global=np.array([0, -0.5, 0]),
        force=np.array([0, 0, 0]),
        # force=np.array([0, 0, 0]),
        torque=np.array([-5, 0, 0]),
        application_point_in_global=np.array([0, 0, 0]),
    )
    fext.add_external_force(
        external_force=force1,
        segment_index=0
    )

    time_steps, all_states, dynamics = drop_the_pendulum(
        model=model,
        Q_init=Q,
        Qdot_init=Qdot,
        external_forces=fext,
        t_final=t_final,
        steps_per_second=60,
    )

    # defects, defects_dot, joint_defects, all_lambdas = post_computations(
    #     model=model,
    #     time_steps=time_steps,
    #     all_states=all_states,
    #     dynamics=dynamics,
    # )

    from viz import plot_series

    # Plot the results
    # the following graphs have to be near zero the more the simulation is long, the more constraints drift from zero
    # plot_series(time_steps, defects, legend="rigid_constraint")  # Phi_r
    # plot_series(time_steps, defects_dot, legend="rigid_constraint_derivative")  # Phi_r_dot
    # plot_series(time_steps, joint_defects, legend="joint_constraint")  # Phi_j
    # the lagrange multipliers are the forces applied to maintain the system (rigidbody and joint constraints)
    # plot_series(time_steps, all_lambdas, legend="lagrange_multipliers")  # lambda

    # animate the motion
    from bionc import Viz

    viz = Viz(model)
    viz.animate(all_states[:12, :], None)
