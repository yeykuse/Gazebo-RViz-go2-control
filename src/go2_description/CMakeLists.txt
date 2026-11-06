cmake_minimum_required(VERSION 3.8)
project(go2_description)

find_package(ament_cmake REQUIRED)

# 安装模型相关目录
foreach(dir config dae launch meshes urdf xacro scripts)
  install(DIRECTORY ${dir}/
    DESTINATION share/${PROJECT_NAME}/${dir})
endforeach()

install(PROGRAMS scripts/standup_publisher.py scripts/go2_keyboard.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
