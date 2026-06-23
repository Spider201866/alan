__all__ = ["AblationUI", "main"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from ablation_ui_lib.app import AblationUI, main

    exports = {"AblationUI": AblationUI, "main": main}
    return exports[name]
