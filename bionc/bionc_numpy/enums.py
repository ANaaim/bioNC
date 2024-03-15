from enum import Enum

from .joints import Joint
from .joints_with_ground import GroundJoint


class JointType(Enum):
    """
    This class represents the different types of joints
    """

    # WELD = "not implemented yet"
    GROUND_FREE = GroundJoint.Free
    GROUND_WELD = GroundJoint.Weld
    GROUND_REVOLUTE = GroundJoint.Hinge
    GROUND_UNIVERSAL = GroundJoint.Universal
    GROUND_SPHERICAL = GroundJoint.Spherical
    CONSTANT_LENGTH = Joint.ConstantLength
    REVOLUTE = Joint.Hinge
    # PRISMATIC = "not implemented yet"
    UNIVERSAL = Joint.Universal
    SPHERICAL = Joint.Spherical
    SPHERE_ON_PLANE = Joint.SphereOnPlane

    # PLANAR = "planar"


class InitialGuessModeType(Enum):
    FROM_CURRENT_MARKERS = "FromCurrentMarkers"
    USER_PROVIDED = "UserProvided"
    USER_PROVIDED_FIRST_FRAME_ONLY = "UserProvidedFirstFrameOnly"
    FROM_FIRST_FRAME_MARKERS = "FromFirstFrameMarkers"
