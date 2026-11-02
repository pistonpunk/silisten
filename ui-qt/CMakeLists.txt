cmake_minimum_required(VERSION 3.21)
project(silisten-qt LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Quick Network)
find_package(LayerShellQt QUIET)

add_executable(silisten-qt main.cpp)

target_link_libraries(silisten-qt PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Quick
    Qt6::Network
)

if (LayerShellQt_FOUND)
    target_link_libraries(silisten-qt PRIVATE LayerShellQt::Interface)
    target_compile_definitions(silisten-qt PRIVATE HAVE_LAYERSHELL)
endif()

add_custom_command(TARGET silisten-qt POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_CURRENT_SOURCE_DIR}/qml
        $<TARGET_FILE_DIR:silisten-qt>/qml
)
