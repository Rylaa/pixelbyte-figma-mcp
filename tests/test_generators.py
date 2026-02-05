"""Tests for code generator fixes."""
from generators.base import MAX_CHILDREN_LIMIT, MAX_NATIVE_CHILDREN_LIMIT, parse_fills, ColorValue, GradientStop, GradientDef, ICON_NAME_MAP
from generators.react_generator import generate_react_code
from generators.css_generator import generate_css_code
import math


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


class TestInnerShadow:
    """Verify INNER_SHADOW includes inset keyword in CSS."""

    def test_react_inner_shadow_has_inset(self, node_with_inner_shadow):
        code = generate_react_code(node_with_inner_shadow, 'InsetBox', use_tailwind=True)
        assert 'inset' in code.lower(), "INNER_SHADOW should include 'inset' keyword"

    def test_react_drop_shadow_no_inset(self):
        node = {
            'type': 'RECTANGLE',
            'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
            'fills': [],
            'strokes': [],
            'effects': [{
                'type': 'DROP_SHADOW', 'visible': True, 'radius': 4, 'spread': 0,
                'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0.25},
                'offset': {'x': 0, 'y': 2}
            }],
            'children': [],
        }
        code = generate_react_code(node, 'DropBox', use_tailwind=True)
        assert 'inset' not in code.lower(), "DROP_SHADOW should NOT include 'inset'"

    def test_react_mixed_shadows(self):
        """Node with both DROP_SHADOW and INNER_SHADOW."""
        node = {
            'type': 'RECTANGLE',
            'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
            'fills': [],
            'strokes': [],
            'effects': [
                {
                    'type': 'DROP_SHADOW', 'visible': True, 'radius': 4, 'spread': 0,
                    'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0.1},
                    'offset': {'x': 0, 'y': 2}
                },
                {
                    'type': 'INNER_SHADOW', 'visible': True, 'radius': 2, 'spread': 0,
                    'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0.2},
                    'offset': {'x': 0, 'y': 1}
                },
            ],
            'children': [],
        }
        code = generate_react_code(node, 'MixedBox', use_tailwind=True)
        # Should have inset for inner, no inset for drop
        assert 'inset' in code.lower(), "Mixed shadows should include 'inset' for INNER_SHADOW"


class TestRadialGradientRadius:
    """Verify radial gradient endRadius scales with dimensions."""

    def test_swiftui_radial_gradient_not_hardcoded_200(self, node_with_radial_gradient):
        """For a 300x150 node, endRadius should be 150 (max/2), not 200."""
        from generators.swiftui_generator import _gradient_to_swiftui
        fills = parse_fills(node_with_radial_gradient)
        gradient = fills[0].gradient
        assert gradient is not None
        assert gradient.type == 'RADIAL'

        # Call with node dimensions
        code, _ = _gradient_to_swiftui(gradient, node_width=300, node_height=150)
        assert 'endRadius: 200' not in code, "endRadius should not be hardcoded to 200"
        assert 'endRadius: 150' in code, "endRadius should be max(300, 150) / 2 = 150"

    def test_swiftui_radial_gradient_square(self):
        """For a 100x100 node, endRadius should be 50."""
        from generators.swiftui_generator import _gradient_to_swiftui
        gradient = GradientDef(
            type='RADIAL',
            stops=[
                GradientStop(color=ColorValue(r=1, g=0, b=0), position=0),
                GradientStop(color=ColorValue(r=0, g=0, b=1), position=1),
            ]
        )
        code, _ = _gradient_to_swiftui(gradient, node_width=100, node_height=100)
        assert 'endRadius: 50' in code

    def test_swiftui_radial_gradient_default_fallback(self):
        """When no dimensions provided, use reasonable default."""
        from generators.swiftui_generator import _gradient_to_swiftui
        gradient = GradientDef(
            type='RADIAL',
            stops=[
                GradientStop(color=ColorValue(r=1, g=0, b=0), position=0),
                GradientStop(color=ColorValue(r=0, g=0, b=1), position=1),
            ]
        )
        code, _ = _gradient_to_swiftui(gradient)  # No dimensions
        assert 'endRadius:' in code
        # Default: use 200 as before (backward compat)
        assert 'endRadius: 200' in code


class TestIconNameMapNoDuplicates:
    """Verify no duplicate keys in ICON_NAME_MAP."""

    def test_trending_maps_to_chart(self):
        """'trending' should map to chart icon, 'fire'/'hot' should map to flame."""
        assert ICON_NAME_MAP['trending'] == 'chart.line.uptrend.xyaxis'
        assert ICON_NAME_MAP['fire'] == 'flame'
        assert ICON_NAME_MAP['hot'] == 'flame'


class TestColorValueHex:
    """Verify ColorValue.hex returns proper hex string."""

    def test_opaque_color_returns_hex(self):
        c = ColorValue(r=1.0, g=0.0, b=0.0, a=1.0)
        assert c.hex == '#ff0000'

    def test_transparent_color_returns_8char_hex(self):
        """Alpha < 1 should return #RRGGBBAA format, not rgba()."""
        c = ColorValue(r=1.0, g=0.0, b=0.0, a=0.5)
        result = c.hex
        assert result.startswith('#'), f"hex should return # prefix, got: {result}"
        assert 'rgba' not in result, f"hex should not return rgba(), got: {result}"

    def test_transparent_color_rgba_property(self):
        """rgba property should return rgba() string."""
        c = ColorValue(r=1.0, g=0.0, b=0.0, a=0.5)
        result = c.rgba
        assert result.startswith('rgba('), f"rgba should return rgba() string, got: {result}"


class TestHardcodedPi:
    """Verify math.pi is used instead of hardcoded value."""

    def test_no_hardcoded_pi_in_base(self):
        with open('generators/base.py', 'r') as f:
            source = f.read()
        assert '3.14159265359' not in source, "Should use math.pi instead of hardcoded value"
