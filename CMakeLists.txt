cmake_minimum_required(VERSION 3.8)
project(CHangmanAI)

find_package(OpenMP REQUIRED)

set(CMAKE_CXX_STANDARD 17)

add_executable(hangman hang.cpp)
target_link_libraries(hangman PRIVATE OpenMP::OpenMP_CXX)
