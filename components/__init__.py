"""Local dependency-free annotation component using Streamlit's V1 protocol."""
from pathlib import Path
from streamlit.components.v1 import declare_component

_corners = declare_component("photomeasure_corners", path=str(Path(__file__).parent / "corners"))


def corner_editor(image_url, size, reference, target, active, revision, key):
    return _corners(image_url=image_url, width=size[0], height=size[1], reference=reference, target=target, active=active, revision=revision, key=key, default=None)
