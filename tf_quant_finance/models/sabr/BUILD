# SABR model

licenses(["notice"])

package(default_visibility = ["//tf_quant_finance:__subpackages__"])

py_library(
    name = "sabr",
    srcs = ["__init__.py"],
    deps = [
        ":sabr_model",
    ],
)

py_library(
    name = "sabr_model",
    srcs = ["sabr_model.py"],
    deps = [
        "//tf_quant_finance/black_scholes:implied_vol_newton_root",
        "//tf_quant_finance/math/random_ops",
        "//tf_quant_finance/models:euler_sampling",
        # tensorflow dep,
    ],
)

py_test(
    name = "sabr_model_test",
    size = "large",
    timeout = "long",
    srcs = ["sabr_model_test.py"],
    python_version = "PY3",
    shard_count = 6,
    deps = [
        ":sabr_model",
        "//tf_quant_finance",
        # test util,
        # absl/testing:parameterized dep,
        # numpy dep,
        # tensorflow dep,
    ],
)
