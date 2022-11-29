cmake_minimum_required(VERSION 3.0.2)
project(ay_py)

find_package(catkin REQUIRED COMPONENTS
  rospy
  )

catkin_package(
  CATKIN_DEPENDS rospy
  )
include_directories(
  ${catkin_INCLUDE_DIRS}
  )
