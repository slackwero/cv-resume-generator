"""The wizard iframes: the PDF preview and the template thumbnails.

Reflex dumps into the `css` object any prop it does not recognize. There the attribute
never reaches the DOM and the iframe is drawn empty, with no error or warning. It is a
silent failure, so every attribute an iframe depends on is checked here.
"""

import reflex as rx

from cv_generator.app.components.wizard_steps import _thumbnail, cv_preview


def _iframes(node: object) -> list[list[str]]:
    """Collects the props of every iframe in the tree, going into the rx.cond branches."""
    found_items: list[list[str]] = []

    if isinstance(node, list):
        for child in node:
            found_items += _iframes(child)
        return found_items

    if not isinstance(node, dict):
        return found_items

    if "iframe" in str(node.get("name", "")):
        found_items.append([str(prop) for prop in node.get("props", [])])

    for key in ("children", "true_value", "false_value"):
        found_items += _iframes(node.get(key))

    return found_items


def _preview_props() -> list[str]:
    props = _iframes(cv_preview().render())
    assert len(props) == 1, "the preview must have exactly one iframe"
    return props[0]


def _thumbnail_props() -> list[str]:
    template = rx.Var("template").to(dict[str, str])
    props = _iframes(_thumbnail(template).render())
    assert len(props) == 1, "the thumbnail must have exactly one iframe"
    return props[0]


def _css(props: list[str]) -> str:
    return " ".join(prop for prop in props if prop.startswith("css:"))


def test_the_preview_points_to_the_pdf_by_src() -> None:
    """The PDF is served by URL: if `src` fell into css, the viewer would stay blank."""
    assert any(prop.startswith("src:") for prop in _preview_props())


def test_the_pdf_url_is_built_in_the_browser() -> None:
    """`get_upload_url` is a browser expression, not text.

    Built in the state with an f-string, the iframe received the Var's representation
    ("<reflex.Var>...</reflex.Var>(getBackendURL(...") and showed "404: Page not found".
    """
    src = next(prop for prop in _preview_props() if prop.startswith("src:"))

    assert "getBackendURL" in src


def test_preview_src_does_not_end_inside_the_styles() -> None:
    assert "src" not in _css(_preview_props()).replace("srcDoc", "")


def test_the_preview_declares_an_accessible_title() -> None:
    """An unnamed iframe is announced only as 'frame' by a screen reader."""
    assert any(prop.startswith("title:") for prop in _preview_props())


def test_the_preview_keeps_its_size() -> None:
    css = _css(_preview_props())

    assert "width" in css
    assert "height" in css


def test_the_thumbnail_carries_the_html_as_srcdoc() -> None:
    """The original case: `srcdoc` is not a recognized prop and ended up inside `css`."""
    assert any(prop.startswith("srcDoc:") for prop in _thumbnail_props())


def test_thumbnail_html_does_not_end_inside_the_styles() -> None:
    assert "srcdoc" not in _css(_thumbnail_props()).lower()


def test_the_thumbnail_is_out_of_the_tab_order() -> None:
    """It is an image of the template; what receives focus and click is the card around it."""
    props = _thumbnail_props()

    assert any("tabIndex" in prop and "-1" in prop for prop in props)
    assert any("aria-hidden" in prop for prop in props)


def test_the_thumbnail_draws_at_page_size_and_scales_down_by_transform() -> None:
    """Rendering at 794x1123 and scaling keeps the layout; shrinking it would reflow it."""
    css = _css(_thumbnail_props())

    assert "794px" in css
    assert "1123px" in css
    assert "scale(" in css
