import numpy as np
from bionc import NaturalCoordinates, SegmentNaturalCoordinates, Viz, SegmentNaturalVelocities, NaturalVelocities

from knee_feikes import create_knee_model
from utils import forward_integration, post_computations

model = create_knee_model()

Q0 = SegmentNaturalCoordinates(
    np.array([1, 0, 0, 0, 0, 0, 0, -0.4, 0, 0, 0, 1])
)
Q1 = SegmentNaturalCoordinates(
    np.array([1, 0, 0, 0, -0.4, 0, 0, -0.8, 0, 0, 0, 1])
)

Q = NaturalCoordinates.from_qi((Q0, Q1))
print(model.rigid_body_constraints(NaturalCoordinates(Q)))
print(model.joint_constraints(NaturalCoordinates(Q)))

viz = Viz(model, size_model_marker=0.004, show_frames=True, show_ground_frame=True, size_xp_marker=0.005)
viz.animate(Q)

# simulation in forward dynamics
tuple_of_Qdot = [
    SegmentNaturalVelocities.from_components(udot=[0, 0, 0], rpdot=[0, 0, 0], rddot=[0, 0, 0], wdot=[0, 0, 0])
    for i in range(0, model.nb_segments)
]
Qdot = NaturalVelocities.from_qdoti(tuple(tuple_of_Qdot))

# actual simulation
t_final = 5  # seconds
time_steps, all_states, dynamics = forward_integration(
    model=model,
    Q_init=Q,
    Qdot_init=Qdot,
    t_final=t_final,
    steps_per_second=100,
)

defects, defects_dot, joint_defects, all_lambdas = post_computations(
    model=model,
    time_steps=time_steps,
    all_states=all_states,
    dynamics=dynamics,
)

# plot results
import matplotlib.pyplot as plt

plt.figure()
for i in range(0, model.nb_rigid_body_constraints):
    plt.plot(time_steps, defects[i, :], marker="o", label=f"defects {i}")
plt.title("Rigid body constraints")
plt.legend()

plt.figure()
for i in range(0, model.nb_joint_constraints):
    plt.plot(time_steps, joint_defects[i, :], marker="o", label=f"joint_defects {i}")
plt.title("Joint constraints")
plt.legend()
plt.show()

# animation
viz = Viz(model)
viz.animate(NaturalCoordinates(all_states[: (12 * model.nb_segments), :]), None)

