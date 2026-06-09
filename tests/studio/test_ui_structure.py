from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest


STUDIO_ROOT = (
    Path(__file__).parents[2] / "src" / "pgm_map_studio" / "studio"
)
TEMPLATE_ROOT = STUDIO_ROOT / "templates"
STATIC_ROOT = STUDIO_ROOT / "static"
PRODUCTION_TEMPLATES = ("dashboard.html", "editor.html", "sketch.html")


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: "_Node | None"):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node] = []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


class _TreeParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__()
        self.root = _Node("document", {}, None)
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        node = _Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in self._VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_TAGS:
            self.current = self.current.parent or self.root

    def handle_endtag(self, tag: str):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent or self.root
        if node is not self.root:
            self.current = node.parent or self.root


def _parse_template(name: str) -> _Node:
    parser = _TreeParser()
    parser.feed((TEMPLATE_ROOT / name).read_text(encoding="utf-8"))
    return parser.root


def _walk(node: _Node):
    yield node
    for child in node.children:
        yield from _walk(child)


@pytest.mark.parametrize("template_name", PRODUCTION_TEMPLATES)
def test_production_templates_do_not_use_inline_styles(template_name):
    root = _parse_template(template_name)

    styled = [node for node in _walk(root) if "style" in node.attrs]

    assert styled == []


@pytest.mark.parametrize(
    ("template_name", "expected"),
    [
        ("dashboard.html", ["tokens.css", "components.css", "editor.css"]),
        ("editor.html", ["tokens.css", "components.css", "editor.css"]),
        ("sketch.html", ["tokens.css", "components.css", "editor.css"]),
        (
            "design.html",
            ["tokens.css", "components.css", "editor.css", "design.css"],
        ),
    ],
)
def test_stylesheets_load_in_ownership_order(template_name, expected):
    text = (TEMPLATE_ROOT / template_name).read_text(encoding="utf-8")
    positions = [text.index(f"filename='{filename}'") for filename in expected]

    assert positions == sorted(positions)


@pytest.mark.parametrize("template_name", ("editor.html", "sketch.html"))
def test_workspace_panels_have_direct_scroll_container(template_name):
    root = _parse_template(template_name)
    panels = [
        node
        for node in _walk(root)
        if node.classes & {"workspace-sidebar", "workspace-inspector"}
    ]

    missing = [
        node.attrs.get("id", node.classes)
        for node in panels
        if not any("workspace-scroll" in child.classes for child in node.children)
    ]

    assert missing == []


@pytest.mark.parametrize("template_name", ("editor.html", "sketch.html"))
def test_workspace_inspectors_have_preceding_resize_handle(template_name):
    root = _parse_template(template_name)
    inspectors = [
        node for node in _walk(root) if "workspace-inspector" in node.classes
    ]

    missing = []
    for inspector in inspectors:
        siblings = inspector.parent.children if inspector.parent else []
        index = siblings.index(inspector)
        previous = siblings[index - 1] if index else None
        if previous is None or "sidebar-handle" not in previous.classes:
            missing.append(inspector.attrs.get("id", "anonymous inspector"))

    assert missing == []


def _selectors(path: Path) -> set[str]:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    selectors = set()
    for selector_group in re.findall(r"([^{}]+)\{[^{}]*\}", text):
        for selector in selector_group.split(","):
            selector = " ".join(selector.split())
            if selector:
                selectors.add(selector)
    return selectors


def test_shared_component_selectors_have_single_css_owner():
    component_selectors = _selectors(STATIC_ROOT / "components.css")
    editor_selectors = _selectors(STATIC_ROOT / "editor.css")
    duplicated = component_selectors & editor_selectors

    assert duplicated == set()


def test_design_gallery_contains_canonical_reference_examples():
    root = _parse_template("design.html")
    classes = [node.classes for node in _walk(root)]

    assert any("workspace" in item for item in classes)
    assert any("workspace-sidebar" in item for item in classes)
    assert any("workspace-inspector" in item for item in classes)
    assert any("workspace-canvas" in item for item in classes)
    assert any("panel-section" in item for item in classes)
    assert any("author-list" in item for item in classes)
    assert any("panel-stack" in item for item in classes)


def test_spawn_inspector_groups_its_sections_in_panel_stack():
    root = _parse_template("editor.html")
    spawn_inspector = next(
        node
        for node in _walk(root)
        if node.attrs.get("id") == "pt-spawn-inspector"
    )

    assert "panel-stack" in spawn_inspector.classes


@pytest.mark.parametrize(
    "template_name",
    ("dashboard.html", "editor.html", "sketch.html", "design.html"),
)
def test_pages_use_shared_shell_classes(template_name):
    root = _parse_template(template_name)
    classes = [node.classes for node in _walk(root)]

    assert any("topbar" in item for item in classes)
    if template_name != "design.html":
        assert any("app-body" in item for item in classes)
        assert any("activity-rail" in item for item in classes)
