load("@my_deps//:requirements.bzl", "requirement")

py_library(
  name = "ticket",
  srcs = ["ticket.py"],
)

py_library(
  name = "calendar",
  deps = [
    ":ticket",
    requirement("ics"),
  ],
  srcs = [
    "calendar.py",
  ],
)

py_library(
  name = "passslot",
  deps = [
    ":ticket",
  ],
  srcs = ["passslot.py"],
  visibility = [
    "//visibility:public",
  ],
)
