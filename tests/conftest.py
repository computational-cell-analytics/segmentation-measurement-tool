"""Shared pytest fixtures and patches for headless CI testing."""
import pytest

_FAKE_GL_EXTENSIONS = frozenset({
    "texture_float",
    "ARB_texture_float",
    "EXT_texture_array",
    "ARB_depth_texture",
    "ARB_framebuffer_object",
    "EXT_framebuffer_object",
})


@pytest.fixture(autouse=True)
def _patch_gl_extensions(monkeypatch):
    """Patch napari's GL extension check so add_image() works headlessly.

    glGetString(GL_EXTENSIONS) returns None when no GL context is current,
    which crashes vispy. We return a static frozenset so the check passes.
    """
    try:
        from napari._vispy.utils import gl as _napari_gl
        monkeypatch.setattr(_napari_gl, "get_gl_extensions", lambda: _FAKE_GL_EXTENSIONS)
    except (ImportError, AttributeError):
        pass

    try:
        from napari._vispy.layers import image as _napari_image
        if hasattr(_napari_image, "get_gl_extensions"):
            monkeypatch.setattr(_napari_image, "get_gl_extensions", lambda: _FAKE_GL_EXTENSIONS)
    except (ImportError, AttributeError):
        pass
