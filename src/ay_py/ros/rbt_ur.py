#! /usr/bin/env python
#Robot controller for Universal Robots UR*.
from const import *

import roslib
import rospy
import actionlib
import control_msgs.msg
import sensor_msgs.msg
import trajectory_msgs.msg
import ur_modern_driver.msg
import copy

from robot import *
from kdl_kin import *
#from rbt_dxlg import TDxlGripper
#from rbt_rq import TRobotiq

'''Robot control class for single Universal Robots UR* with an empty gripper.'''
class TRobotUR(TMultiArmRobot):
  def __init__(self, name='UR', is_sim=False):
    super(TRobotUR,self).__init__(name=name)
    self.is_sim= is_sim

    self.joint_names= [[]]
    #self.joint_names[0]= rospy.get_param('controller_joint_names')
    self.joint_names[0]= ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
                          'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint']

    #UR all link names:
    #obtained from ay_py/demo_ros/kdl1.py (URDF link names)
    self.links= {}
    self.links['base']= ['base_link']
    self.links['r_arm']= ['shoulder_link', 'upper_arm_link', 'forearm_link', 'wrist_1_link', 'wrist_2_link', 'wrist_3_link']
    self.links['robot']= self.links['base'] + self.links['r_arm']

    #Thread locker for robot_mode_state:
    self.robotmodestate_locker= threading.RLock()

  '''Initialize (e.g. establish ROS connection).'''
  def Init(self):
    self._is_initialized= False
    res= []
    ra= lambda r: res.append(r)

    #Check the validity of joint positions:
    try:
      x_curr= rospy.wait_for_message('/joint_states', sensor_msgs.msg.JointState, 3.0)
      if not all([-1.25*math.pi<q and q<1.25*math.pi for q in x_curr.position]):
        CPrint(4,'''Warning: some joint angles exceed the expected range.
  Joint angles = {q}
  Running without notifying is very dangerous.
  Manually moving joints to proper range (-1.25*math.pi, 1.25*math.pi)
  is highly recommended.
  Hint: Use the Freedrive mode with observing the /joint_states topic by:
    $ rostopic echo '/joint_states/position[5]'

  Will you abort setting up the robot? (Recommended: Y)'''.format(q=x_curr.position))
        if AskYesNo():  return False
    except (rospy.ROSException, rospy.ROSInterruptException):
      CPrint(4,'Cannot get data from /joint_states')
      return False

    self.kin= [None]
    self.kin[0]= TKinematics(base_link='base_link',end_link='tool0')

    #ra(self.AddPub('joint_path_command', '/joint_path_command', trajectory_msgs.msg.JointTrajectory))

    ra(self.AddActC('traj', '/follow_joint_trajectory',
                    control_msgs.msg.FollowJointTrajectoryAction, time_out=3.0))

    #if self.is_sim:
      #ra(self.AddPub('joint_states', '/joint_states', sensor_msgs.msg.JointState))

    ra(self.AddSub('joint_states', '/joint_states', sensor_msgs.msg.JointState, self.JointStatesCallback))

    if not self.is_sim:
      ra(self.AddSub('robot_mode_state', '/ur_driver/robot_mode_state', ur_modern_driver.msg.RobotModeDataMsg, self.RobotModeStateCallback))

    #self.robotiq= TRobotiq()  #Robotiq controller
    #self.grippers= [self.robotiq]
    self.grippers= [TFakeGripper()]

    #print 'Enabling the robot...'

    #print 'Initializing and activating Robotiq gripper...'
    #ra(self.robotiq.Init())

    if False not in res:  self._is_initialized= True
    return self._is_initialized

  def Cleanup(self):
    #NOTE: cleaning-up order is important. consider dependency
    super(TRobotUR,self).Cleanup()

  '''Configure a state validity checker.'''
  def ConfigureSVC(self, c):
    c.JointNames= copy.deepcopy(self.joint_names)
    c.Links= copy.deepcopy(self.links)
    c.PaddingLinks= []
    c.PaddingValues= [0.002]*len(c.PaddingLinks)
    c.DefaultBaseFrame= 'base_link'
    c.HandLinkToGrasp[0]= 'tool0'
    c.IgnoredLinksInGrasp[0]= []

  '''Answer to a query q by {True,False}. e.g. Is('PR2').'''
  def Is(self, q):
    if q in ('UR','UR_SIM','UR3'):  return True
    return super(TRobotUR,self).Is(q)

  #Check if the robot is normal state (i.e. running properly without stopping).
  def IsNormal(self):
    if self.is_sim:  return True
    with self.robotmodestate_locker:
      return all((self.robot_mode_state.is_ready, not self.robot_mode_state.is_emergency_stopped, not self.robot_mode_state.is_protective_stopped))

  @property
  def NumArms(self):
    return 1

  @property
  def BaseFrame(self):
    return 'base_link'

  '''End link of an arm.'''
  def EndLink(self, arm=None):
    return 'tool0'

  '''Names of joints of an arm.'''
  def JointNames(self, arm=None):
    arm= 0
    return self.joint_names[arm]

  def DoF(self, arm=None):
    return 6

  '''Return limits (lower, upper) of joint angles.
    arm: arm id, or None (==currarm). '''
  def JointLimits(self, arm=None):
    arm= 0
    return self.kin[arm].joint_limits_lower, self.kin[arm].joint_limits_upper

  '''Return limits of joint angular velocity.
    arm: arm id, or None (==currarm). '''
  def JointVelLimits(self, arm=None):
    #max_velocity (UR3,5,10) = 10 rad/s (according to ur_modern_driver/launch/*.launch)
    #FIXME: Should be adjusted for UR
    return [0.5, 0.5, 0.8, 0.8, 0.8, 0.8, 0.8]

  '''Return range of gripper.
    arm: arm id, or None (==currarm). '''
  def GripperRange(self, arm=None):
    arm= 0
    return self.grippers[arm].PosRange()

  '''End effector of an arm.'''
  def EndEff(self, arm=None):
    arm= 0
    return self.grippers[arm]

  def JointStatesCallback(self, msg):
    with self.sensor_locker:
      self.x_curr= msg
      self.q_curr= self.x_curr.position
      self.dq_curr= self.x_curr.velocity

  def RobotModeStateCallback(self, msg):
    with self.robotmodestate_locker:
      self.robot_mode_state= msg

  '''Return joint angles of an arm.
    arm: arm id, or None (==currarm). '''
  def Q(self, arm=None):
    with self.sensor_locker:
      q= self.q_curr
    return list(q)

  '''Return joint velocities of an arm.
    arm: arm id, or None (==currarm). '''
  def DQ(self, arm=None):
    with self.sensor_locker:
      dq= self.dq_curr
    return list(dq)

  '''Compute a forward kinematics of an arm.
  Return self.EndLink(arm) pose on self.BaseFrame.
    return: x, res;  x: pose (None if failure), res: FK status.
    arm: arm id, or None (==currarm).
    q: list of joint angles, or None (==self.Q(arm)).
    x_ext: a local pose on self.EndLink(arm) frame.
      If not None, the returned pose is x_ext on self.BaseFrame.
    with_st: whether return FK status. '''
  def FK(self, q=None, x_ext=None, arm=None, with_st=False):
    arm= 0
    if q is None:  q= self.Q(arm)

    angles= {joint:q[j] for j,joint in enumerate(self.joint_names[arm])}  #Deserialize
    with self.sensor_locker:
      x= self.kin[arm].forward_position_kinematics(joint_values=angles)

    x_res= x if x_ext is None else Transform(x,x_ext)
    return (x_res, True) if with_st else x_res

  '''Compute a Jacobian matrix of an arm.
  Return J of self.EndLink(arm).
    return: J, res;  J: Jacobian (None if failure), res: status.
    arm: arm id, or None (==currarm).
    q: list of joint angles, or None (==self.Q(arm)).
    x_ext: a local pose (i.e. offset) on self.EndLink(arm) frame.
      If not None, we do not consider an offset.
    with_st: whether return the solver status. '''
  def J(self, q=None, x_ext=None, arm=None, with_st=False):
    arm= 0
    if q is None:  q= self.Q(arm)

    if x_ext is not None:
      #Since KDL does not provide Jacobian computation with an offset x_ext,
      #and converting J with x_ext is not simple, we raise an Exception.
      #TODO: Implement our own FK to solve this issue.
      raise Exception('TRobotUR.J: Jacobian with x_ext is not implemented yet.')

    angles= {joint:q[j] for j,joint in enumerate(self.joint_names[arm])}  #Deserialize
    with self.sensor_locker:
      J_res= self.kin[arm].jacobian(joint_values=angles)
    return (J_res, True) if with_st else J_res

  '''Compute an inverse kinematics of an arm.
  Return joint angles for a target self.EndLink(arm) pose on self.BaseFrame.
    return: q, res;  q: joint angles (None if failure), res: IK status.
    arm: arm id, or None (==currarm).
    x_trg: target pose.
    x_ext: a local pose on self.EndLink(arm) frame.
      If not None, the returned q satisfies self.FK(q,x_ext,arm)==x_trg.
    start_angles: initial joint angles for IK solver, or None (==self.Q(arm)).
    with_st: whether return IK status. '''
  def IK(self, x_trg, x_ext=None, start_angles=None, arm=None, with_st=False):
    arm= 0
    if start_angles is None:  start_angles= self.Q(arm)

    x_trg[3:]/= la.norm(x_trg[3:])  #Normalize the orientation:
    xw_trg= x_trg if x_ext is None else TransformRightInv(x_trg,x_ext)

    with self.sensor_locker:
      res,q= self.kin[arm].inverse_kinematics(xw_trg[:3], xw_trg[3:], seed=start_angles, maxiter=1000, eps=1.0e-6, with_st=True)

    if res:  return (q, True) if with_st else q
    else:  return (q, False) if with_st else None


  '''Follow a joint angle trajectory.
    arm: arm id, or None (==currarm).
    q_traj: joint angle trajectory [q0,...,qD]*N.
    t_traj: corresponding times in seconds from start [t1,t2,...,tN].
    blocking: False: move background, True: wait until motion ends, 'time': wait until tN. '''
  def FollowQTraj(self, q_traj, t_traj, arm=None, blocking=False):
    assert(len(q_traj)==len(t_traj))
    arm= 0

    if not self.IsNormal():
      raise Exception('Cannot execute FollowQTraj as the robot is not normal state.')

    #Insert current position to beginning.
    if t_traj[0]>1.0e-4:
      t_traj.insert(0,0.0)
      q_traj.insert(0,self.Q(arm=arm))

    dq_traj= QTrajToDQTraj(q_traj, t_traj)

    #copy q_traj, t_traj to goal
    goal= control_msgs.msg.FollowJointTrajectoryGoal()
    goal.goal_time_tolerance= rospy.Time(0.1)
    goal.trajectory.joint_names= self.joint_names[arm]
    goal.trajectory= ToROSTrajectory(self.JointNames(arm), q_traj, t_traj, dq_traj)

    with self.control_locker:
      actc= self.actc.traj
      actc.send_goal(goal)
      BlockAction(actc, blocking=blocking, duration=t_traj[-1])


  '''Open a gripper.
    arm: arm id, or None (==currarm).
    blocking: False: move background, True: wait until motion ends.  '''
  def OpenGripper(self, arm=None, blocking=False):
    if self.is_sim:  return  #WARNING:We do nothing if the robot is on simulator.
    if arm is None:  arm= self.Arm
    gripper= self.grippers[arm]
    with self.control_locker:
      gripper.Open(blocking=blocking)

  '''Close a gripper.
    arm: arm id, or None (==currarm).
    blocking: False: move background, True: wait until motion ends.  '''
  def CloseGripper(self, arm=None, blocking=False):
    if self.is_sim:  return  #WARNING:We do nothing if the robot is on simulator.
    if arm is None:  arm= self.Arm
    gripper= self.grippers[arm]
    with self.control_locker:
      gripper.Close(blocking=blocking)

  '''High level interface to control a gripper.
    arm: arm id, or None (==currarm).
    pos: target position in meter.
    max_effort: maximum effort to control; 0 (weakest), 100 (strongest).
    speed: speed of the movement; 0 (minimum), 100 (maximum).
    blocking: False: move background, True: wait until motion ends.  '''
  def MoveGripper(self, pos, max_effort=50.0, speed=50.0, arm=None, blocking=False):
    if self.is_sim:  return  #WARNING:We do nothing if the robot is on simulator.
    arm= 0

    gripper= self.grippers[arm]
    with self.control_locker:
      gripper.Move(pos, max_effort, speed, blocking=blocking)

  '''Get a gripper position in meter.
    arm: arm id, or None (==currarm). '''
  def GripperPos(self, arm=None):
    if self.is_sim:  return 0.0  #WARNING:We do nothing if the robot is on simulator.
    arm= 0

    gripper= self.grippers[arm]
    with self.sensor_locker:
      pos= gripper.Position()
    return pos

  '''Get fingertip offset in meter.
    The fingertip trajectory of Robotiq gripper has a round shape.
    This function gives the offset from the opening posture.
      pos: Gripper position to get the offset. None: Current position.
      arm: arm id, or None (==currarm).'''
  def FingertipOffset(self, pos=None, arm=None):
    arm= 0
    gripper= self.grippers[arm]
    if gripper.Is('Robotiq'):
      if pos is None:  pos= self.GripperPos(arm)
      return -0.701*pos**3 - 2.229*pos**2 + 0.03*pos + 0.128 - 0.113
    else:
      return 0.0

