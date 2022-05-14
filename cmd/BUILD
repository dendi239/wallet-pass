load("@my_deps//:requirements.bzl", "requirement")

py_binary(
  name = "bot",
  deps = [
    "//uz:parse",
    "//lib:passslot",
    requirement("textract"),
  ],
  srcs = ["bot.py"],
)

py_binary(
  name = "main",
  deps = [
    ":bot",
    requirement("textract"),
  ],
  srcs = ["main.py"],
  python_version = "PY3",
)
