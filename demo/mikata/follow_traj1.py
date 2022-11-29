#!/usr/bin/python
#Following a trajectory.

from _path import *
from ay_py.misc.dxl_mikata import *

#Setup the device
mikata= TMikata()
mikata.Setup()
mikata.EnableTorque()

#More effort to follow trajectory.
mikata.SetPWM({jname:e for e,jname in zip([50,50,50,50,50],mikata.JointNames())})

#q_traj= [[0, 0, 1, -1.3, 0],
  #[0.6504078592, 0.0935728288, 0.7179030143999999, -0.9694758656, 0.07056311679999999],
  #[-0.6734175712, -0.4740000672, 1.0369710208, -0.9694758656, 0.0674951552],
  #[-0.0966407904, -0.8544273056, 0.8191457472, 0.80533992, 0.0828349632],
  #[-0.0582912704, 0.0628932128, 0.8222137088, -0.8268156512, 0.0429514624],
  #[0, 0, 1, -1.3, 0]]
q_traj= [[0, 0, 1, -1.3, 0],
  [-0.0015339808, 0.245436928, 0.782330208, -1.3637089312, 0.0322135968],
  [0.4924078368, 0.5123495872, 0.7485826304, -1.4373400096, 0.0475534048],
  [-0.4003689888, 0.4740000672, 0.851359344, -1.6244856671999999, 0.0628932128],
  [-0.1257864256, -1.1612234656, 1.1029321952, -0.35434956479999996, 0.053689328],
  [0, 0, 1, -1.3, 0]]
t_traj= [2.0,3.0,4.0,5.0,7.0,9.0]

print(q_traj)
print(t_traj)

mikata.FollowTrajectory(mikata.JointNames(), q_traj, t_traj, blocking=True)

#mikata.DisableTorque()
mikata.Quit()
