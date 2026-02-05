"""Tests for code generator fixes."""
from generators.base import MAX_CHILDREN_LIMIT, MAX_NATIVE_CHILDREN_LIMIT
from generators.react_generator import generate_react_code
from generators.css_generator import generate_css_code


class TestChildLimitsConsistency:
    """Verify child limits are consistent across modules."""

    def test_web_child_limit_is_20(self):
        assert MAX_CHILDREN_LIMIT == 20

    def test_native_child_limit_is_15(self):
        assert MAX_NATIVE_CHILDREN_LIMIT == 15

    def test_figma_mcp_imports_from_base(self):
        """figma_mcp.py should import limits from base.py, not define its own."""
        import importlib.util
        import inspect
        # Read figma_mcp.py source
        with open('figma_mcp.py', 'r') as f:
            source = f.read()
        # Should NOT have standalone MAX_CHILDREN_LIMIT = <number> assignment
        import re
        standalone_defs = re.findall(r'^MAX_CHILDREN_LIMIT\s*=\s*\d+', source, re.MULTILINE)
        assert len(standalone_defs) == 0, f"figma_mcp.py still defines its own MAX_CHILDREN_LIMIT: {standalone_defs}"


class TestDashedBorder:
    """Verify dashed borders are rendered correctly."""

    def test_react_dashed_border(self, node_with_dashed_stroke):
        code = generate_react_code(node_with_dashed_stroke, 'DashedBox', use_tailwind=True)
        assert 'dashed' in code.lower(), "React should render dashed border style"

    def test_react_solid_border_no_dashes(self):
        node = {
            'type': 'RECTANGLE',
            'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
            'fills': [],
            'strokes': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0, 'g': 0, 'b': 0, 'a': 1}, 'opacity': 1}],
            'strokeWeight': 1,
            'strokeAlign': 'INSIDE',
            'effects': [],
            'children': [],
        }
        code = generate_react_code(node, 'SolidBox', use_tailwind=True)
        assert 'border-' in code
        assert 'dashed' not in code.lower()

    def test_css_dashed_border(self, node_with_dashed_stroke):
        code = generate_css_code(node_with_dashed_stroke, 'dashed-box')
        assert 'dashed' in code.lower(), "CSS should render border-style: dashed"

    def test_css_solid_border_no_dashes(self):
        node = {
            'type': 'RECTANGLE',
            'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
            'fills': [],
            'strokes': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0, 'g': 0, 'b': 0, 'a': 1}, 'opacity': 1}],
            'strokeWeight': 1,
            'strokeAlign': 'INSIDE',
            'effects': [],
            'children': [],
        }
        code = generate_css_code(node, 'solid-box')
        assert 'solid' in code.lower()


class TestIndividualBorderWidths:
    """Verify individual border widths are used when present."""

    def test_react_individual_borders(self, node_with_individual_borders):
        code = generate_react_code(node_with_individual_borders, 'IndBorders', use_tailwind=True)
        # Should have individual border widths, not uniform
        assert 'border-t-' in code or 'borderTopWidth' in code, "React should render individual top border"
        assert 'border-b-' in code or 'borderBottomWidth' in code, "React should render individual bottom border"

    def test_css_individual_borders(self, node_with_individual_borders):
        code = generate_css_code(node_with_individual_borders, 'ind-borders')
        assert 'border-top-width' in code or 'border-top:' in code, "CSS should render individual top border"
        assert 'border-bottom-width' in code or 'border-bottom:' in code, "CSS should render individual bottom border"


class TestBackdropBlur:
    """Verify BACKGROUND_BLUR uses backdrop-filter, not filter."""

    def test_react_background_blur_uses_backdrop_filter(self, node_with_background_blur):
        code = generate_react_code(node_with_background_blur, 'BlurBox', use_tailwind=True)
        assert 'backdropFilter' in code or 'backdrop-blur' in code, \
            "BACKGROUND_BLUR should use backdropFilter, not filter"
        assert "filter: 'blur" not in code, \
            "BACKGROUND_BLUR should NOT use filter property"

    def test_react_layer_blur_uses_filter(self):
        node = {
            'type': 'RECTANGLE',
            'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
            'fills': [],
            'strokes': [],
            'effects': [{'type': 'LAYER_BLUR', 'visible': True, 'radius': 8}],
            'children': [],
        }
        code = generate_react_code(node, 'LayerBlurBox', use_tailwind=True)
        assert "filter:" in code, "LAYER_BLUR should use filter property"
