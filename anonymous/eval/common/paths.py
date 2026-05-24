import re


_PATH_COMPONENT_RE = re.compile(r"[^\w_. -]")


def sanitize_path_component(component: str) -> str:
    return _PATH_COMPONENT_RE.sub("_", component)
