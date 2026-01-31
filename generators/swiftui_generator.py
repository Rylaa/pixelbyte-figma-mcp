"""
SwiftUI Code Generator - Recursive rendering with full property support.

Generates production-quality SwiftUI code from Figma node trees.
Supports: fills (solid, gradient, image), strokes, corner radius, shadows,
blur, opacity, blend modes, rotation, padding, auto-layout, text styling.
"""

from typing import Dict, Any

# Import helpers from base module
from generators.base import (
    hex_to_rgb,
    parse_fills, parse_stroke, parse_corners, parse_effects, parse_layout,
    parse_text_style, parse_style_bundle,
    ColorValue, GradientDef, GradientStop, FillLayer, StrokeInfo, CornerRadii,
    ShadowEffect, BlurEffect, LayoutInfo, TextStyle, StyleBundle,
    SWIFTUI_WEIGHT_MAP, MAX_NATIVE_CHILDREN_LIMIT, MAX_DEPTH,
)



# ---------------------------------------------------------------------------
# Task 2: Recursive node dispatcher
# ---------------------------------------------------------------------------

def _generate_swiftui_node(node: Dict[str, Any], indent: int = 8, depth: int = 0) -> str:
    """Recursively generate SwiftUI code for a single node with full property support."""
    if depth > MAX_DEPTH:
        return ''

    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')
    prefix = ' ' * indent

    if node_type == 'TEXT':
        return _swiftui_text_node(node, indent)
    elif node_type in ('RECTANGLE', 'ELLIPSE', 'LINE', 'STAR', 'REGULAR_POLYGON'):
        return _swiftui_shape_node(node, indent)
    elif node_type == 'VECTOR':
        return _swiftui_vector_node(node, indent)
    elif node_type in ('FRAME', 'GROUP', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE', 'SECTION'):
        return _swiftui_container_node(node, indent, depth)
    else:
        # Unknown type - render as comment
        return f'{prefix}// Unsupported: {node_type} "{name}"'


# ---------------------------------------------------------------------------
# Task 3: Modifier builders
# ---------------------------------------------------------------------------

def _swiftui_fill_modifier(node: Dict[str, Any]) -> tuple[str, str]:
    """Generate SwiftUI background/fill modifier and any gradient definitions.
    Returns (modifier_code, gradient_definition).
    """
    fills = node.get('fills', [])
    modifier = ''
    gradient_def = ''

    for fill in fills:
        if not fill.get('visible', True):
            continue
        fill_type = fill.get('type', '')

        if fill_type == 'SOLID':
            color = fill.get('color', {})
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            if a < 1:
                modifier = f'.background(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f}))'
            else:
                modifier = f'.background(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}))'
            break

        elif fill_type == 'GRADIENT_LINEAR':
            stops = fill.get('gradientStops', [])
            if stops:
                stop_strs = []
                for stop in stops:
                    pos = stop.get('position', 0)
                    c = stop.get('color', {})
                    stop_strs.append(
                        f"            .init(color: Color(red: {c.get('r', 0):.3f}, green: {c.get('g', 0):.3f}, blue: {c.get('b', 0):.3f}), location: {pos:.2f})"
                    )
                stops_code = ',\n'.join(stop_strs)
                # Calculate direction from handle positions
                handles = fill.get('gradientHandlePositions', [])
                start, end = _gradient_direction_swiftui(handles)
                gradient_def = f"        let gradient = LinearGradient(\n            stops: [\n{stops_code}\n            ],\n            startPoint: {start},\n            endPoint: {end}\n        )"
                modifier = '.background(gradient)'
            break

        elif fill_type == 'GRADIENT_RADIAL':
            stops = fill.get('gradientStops', [])
            if stops:
                stop_strs = []
                for stop in stops:
                    pos = stop.get('position', 0)
                    c = stop.get('color', {})
                    stop_strs.append(
                        f"            .init(color: Color(red: {c.get('r', 0):.3f}, green: {c.get('g', 0):.3f}, blue: {c.get('b', 0):.3f}), location: {pos:.2f})"
                    )
                stops_code = ',\n'.join(stop_strs)
                bbox = node.get('absoluteBoundingBox', {})
                radius = max(bbox.get('width', 100), bbox.get('height', 100)) / 2
                gradient_def = f"        let gradient = RadialGradient(\n            stops: [\n{stops_code}\n            ],\n            center: .center,\n            startRadius: 0,\n            endRadius: {radius:.0f}\n        )"
                modifier = '.background(gradient)'
            break

    return modifier, gradient_def


def _gradient_direction_swiftui(handles: list) -> tuple[str, str]:
    """Convert Figma gradient handle positions to SwiftUI UnitPoint."""
    if not handles or len(handles) < 2:
        return '.leading', '.trailing'

    start_x = handles[0].get('x', 0)
    start_y = handles[0].get('y', 0)
    end_x = handles[1].get('x', 1)
    end_y = handles[1].get('y', 0)

    def to_unit_point(x, y):
        # Map to nearest SwiftUI UnitPoint
        if x <= 0.2 and y <= 0.2: return '.topLeading'
        if x >= 0.8 and y <= 0.2: return '.topTrailing'
        if x <= 0.2 and y >= 0.8: return '.bottomLeading'
        if x >= 0.8 and y >= 0.8: return '.bottomTrailing'
        if y <= 0.2: return '.top'
        if y >= 0.8: return '.bottom'
        if x <= 0.2: return '.leading'
        if x >= 0.8: return '.trailing'
        return '.center'

    return to_unit_point(start_x, start_y), to_unit_point(end_x, end_y)


def _swiftui_stroke_modifier(node: Dict[str, Any]) -> str:
    """Generate SwiftUI stroke/border modifier."""
    stroke_data = parse_stroke(node)
    if not stroke_data:
        return ''

    weight = stroke_data.get('weight', 0)
    if not weight:
        return ''

    colors = stroke_data.get('colors', [])
    if not colors:
        return ''

    first = colors[0]
    if first.get('type') != 'SOLID':
        return ''

    hex_color = first.get('hex', '#000000')
    rgb = hex_to_rgb(hex_color)
    opacity = first.get('opacity', 1)

    color_code = f"Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f})"
    if opacity < 1:
        color_code += f".opacity({opacity:.2f})"

    radii = parse_corners(node)
    corner = int(radii['topLeft']) if radii and radii.get('isUniform') else 0
    return f".overlay(RoundedRectangle(cornerRadius: {corner}).stroke({color_code}, lineWidth: {weight}))"


def _swiftui_corner_modifier(node: Dict[str, Any]) -> str:
    """Generate SwiftUI corner radius modifier."""
    radii = parse_corners(node)
    if not radii:
        return ''

    if radii.get('isUniform'):
        tl = radii['topLeft']
        if tl > 0:
            return f".cornerRadius({int(tl)})"
        return ''
    else:
        tl = int(radii['topLeft'])
        tr = int(radii['topRight'])
        br = int(radii['bottomRight'])
        bl = int(radii['bottomLeft'])
        return f".clipShape(RoundedCorner(topLeft: {tl}, topRight: {tr}, bottomRight: {br}, bottomLeft: {bl}))"


def _swiftui_effects_modifier(node: Dict[str, Any]) -> list[str]:
    """Generate SwiftUI shadow and blur modifiers."""
    effects_data = parse_effects(node)
    modifiers = []

    shadows = effects_data.get('shadows') or []
    blurs = effects_data.get('blurs') or []

    for shadow in shadows:
        if shadow.get('type') == 'DROP_SHADOW':
            color = shadow.get('hex', '#000000')
            rgb = hex_to_rgb(color)
            offset = shadow.get('offset', {'x': 0, 'y': 0})
            radius = shadow.get('radius', 0)
            opacity = shadow.get('opacity', 0.25)
            modifiers.append(
                f".shadow(color: Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f}).opacity({opacity:.2f}), "
                f"radius: {int(radius)}, x: {int(offset.get('x', 0))}, y: {int(offset.get('y', 0))})"
            )
        elif shadow.get('type') == 'INNER_SHADOW':
            # SwiftUI doesn't have native inner shadow - use overlay approach
            modifiers.append(f"// Inner shadow: use .overlay with inverted mask")

    for blur in blurs:
        blur_type = blur.get('type', '')
        radius = blur.get('radius', 0)
        if blur_type == 'LAYER_BLUR':
            modifiers.append(f".blur(radius: {int(radius)})")
        elif blur_type == 'BACKGROUND_BLUR':
            modifiers.append(f"// Background blur: use .background(.ultraThinMaterial)")

    return modifiers


def _swiftui_appearance_modifiers(node: Dict[str, Any]) -> list[str]:
    """Generate opacity, blend mode, rotation modifiers."""
    modifiers = []

    opacity = node.get('opacity', 1)
    if opacity < 1:
        modifiers.append(f".opacity({opacity:.2f})")

    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_map = {
        'MULTIPLY': '.multiply', 'SCREEN': '.screen', 'OVERLAY': '.overlay',
        'DARKEN': '.darken', 'LIGHTEN': '.lighten', 'COLOR_DODGE': '.colorDodge',
        'COLOR_BURN': '.colorBurn', 'SOFT_LIGHT': '.softLight', 'HARD_LIGHT': '.hardLight',
        'DIFFERENCE': '.difference', 'EXCLUSION': '.exclusion'
    }
    if blend_mode in blend_map:
        modifiers.append(f".blendMode({blend_map[blend_mode]})")

    rotation = node.get('rotation', 0)
    if rotation:
        modifiers.append(f".rotationEffect(.degrees({rotation:.1f}))")

    return modifiers


def _swiftui_collect_modifiers(node: Dict[str, Any], include_frame: bool = True) -> tuple[list[str], str]:
    """Collect all modifiers for a node. Returns (modifiers_list, gradient_definition)."""
    modifiers = []
    gradient_def = ''

    # Frame/size
    if include_frame:
        bbox = node.get('absoluteBoundingBox', {})
        w = int(bbox.get('width', 0))
        h = int(bbox.get('height', 0))
        if w and h:
            modifiers.append(f".frame(width: {w}, height: {h})")

    # Background/fill
    fill_mod, gradient_def = _swiftui_fill_modifier(node)
    if fill_mod:
        modifiers.append(fill_mod)

    # Corner radius
    corner_mod = _swiftui_corner_modifier(node)
    if corner_mod:
        modifiers.append(corner_mod)

    # Stroke/border
    stroke_mod = _swiftui_stroke_modifier(node)
    if stroke_mod:
        modifiers.append(stroke_mod)

    # Effects (shadow, blur)
    modifiers.extend(_swiftui_effects_modifier(node))

    # Appearance (opacity, blend, rotation)
    modifiers.extend(_swiftui_appearance_modifiers(node))

    # Padding
    pt = node.get('paddingTop', 0)
    pr = node.get('paddingRight', 0)
    pb = node.get('paddingBottom', 0)
    pl = node.get('paddingLeft', 0)
    if pt or pr or pb or pl:
        if pt == pr == pb == pl and pt > 0:
            modifiers.append(f".padding({int(pt)})")
        else:
            modifiers.append(f".padding(EdgeInsets(top: {int(pt)}, leading: {int(pl)}, bottom: {int(pb)}, trailing: {int(pr)}))")

    # Clip content
    if node.get('clipsContent', False):
        modifiers.append(".clipped()")

    return modifiers, gradient_def


# ---------------------------------------------------------------------------
# Task 4: Text node renderer
# ---------------------------------------------------------------------------

def _swiftui_text_node(node: Dict[str, Any], indent: int) -> str:
    """Generate SwiftUI Text view with full styling."""
    prefix = ' ' * indent
    lines = []

    text = node.get('characters', node.get('name', ''))
    style = node.get('style', {})
    fills = node.get('fills', [])

    font_size = style.get('fontSize', 16)
    font_weight = style.get('fontWeight', 400)
    font_family = style.get('fontFamily', '')
    line_height = style.get('lineHeightPx')
    letter_spacing = style.get('letterSpacing', 0)
    text_align = style.get('textAlignHorizontal', 'LEFT')
    text_case = style.get('textCase', 'ORIGINAL')
    text_decoration = style.get('textDecoration', 'NONE')

    # Hyperlink
    hyperlink = node.get('hyperlink')
    hyperlink_url = None
    if hyperlink and hyperlink.get('type') == 'URL':
        hyperlink_url = hyperlink.get('url', '')

    weight = SWIFTUI_WEIGHT_MAP.get(font_weight, '.regular')

    # Escape text for Swift string literal
    escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    # Text or Link
    if hyperlink_url:
        lines.append(f'{prefix}Link("{escaped_text}", destination: URL(string: "{hyperlink_url}")!)')
    else:
        lines.append(f'{prefix}Text("{escaped_text}")')

    # Font
    if font_family:
        lines.append(f'{prefix}    .font(.custom("{font_family}", size: {font_size}))')
        lines.append(f'{prefix}    .fontWeight({weight})')
    else:
        lines.append(f'{prefix}    .font(.system(size: {font_size}, weight: {weight}))')

    # Text color from fills
    for fill in fills:
        if fill.get('visible', True) and fill.get('type') == 'SOLID':
            color = fill.get('color', {})
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            if a < 1:
                lines.append(f'{prefix}    .foregroundColor(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f}))')
            else:
                lines.append(f'{prefix}    .foregroundColor(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}))')
            break

    # Line height (via lineSpacing approximation)
    if line_height and font_size:
        line_spacing = line_height - font_size
        if line_spacing > 0:
            lines.append(f'{prefix}    .lineSpacing({line_spacing:.1f})')

    # Letter spacing / tracking
    if letter_spacing and letter_spacing != 0:
        lines.append(f'{prefix}    .tracking({letter_spacing:.2f})')

    # Text alignment
    align_map = {'LEFT': '.leading', 'CENTER': '.center', 'RIGHT': '.trailing', 'JUSTIFIED': '.leading'}
    if text_align in align_map and text_align != 'LEFT':
        lines.append(f'{prefix}    .multilineTextAlignment({align_map[text_align]})')

    # Text case
    case_map = {'UPPER': '.uppercase', 'LOWER': '.lowercase'}
    if text_case in case_map:
        lines.append(f'{prefix}    .textCase({case_map[text_case]})')

    # Text decoration
    if text_decoration == 'UNDERLINE':
        lines.append(f'{prefix}    .underline()')
    elif text_decoration == 'STRIKETHROUGH':
        lines.append(f'{prefix}    .strikethrough()')

    # Max lines
    max_lines = style.get('maxLines')
    text_truncation = style.get('textTruncation', 'DISABLED')
    if max_lines and max_lines > 0:
        lines.append(f'{prefix}    .lineLimit({max_lines})')
        if text_truncation == 'ENDING':
            lines.append(f'{prefix}    .truncationMode(.tail)')

    # Opacity
    opacity = node.get('opacity', 1)
    if opacity < 1:
        lines.append(f'{prefix}    .opacity({opacity:.2f})')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Task 5: Shape node renderer
# ---------------------------------------------------------------------------

def _swiftui_shape_node(node: Dict[str, Any], indent: int) -> str:
    """Generate SwiftUI shape view (Rectangle, Ellipse, etc.) with full styling."""
    prefix = ' ' * indent
    lines = []
    node_type = node.get('type', 'RECTANGLE')

    # Determine shape
    if node_type == 'ELLIPSE':
        shape_name = 'Circle' if _is_circle(node) else 'Ellipse'
    elif node_type == 'LINE':
        shape_name = 'Divider'
    else:
        # Rectangle, Star, Polygon - use RoundedRectangle if has corner radius
        corner_radii = parse_corners(node)
        if corner_radii and corner_radii.get('isUniform') and corner_radii['topLeft'] > 0:
            shape_name = f"RoundedRectangle(cornerRadius: {int(corner_radii['topLeft'])})"
        else:
            shape_name = 'Rectangle'

    # Fill
    fills = node.get('fills', [])
    fill_code = ''
    for fill in fills:
        if not fill.get('visible', True):
            continue
        if fill.get('type') == 'SOLID':
            color = fill.get('color', {})
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            if a < 1:
                fill_code = f".fill(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f}))"
            else:
                fill_code = f".fill(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}))"
            break
        elif fill.get('type', '').startswith('GRADIENT_'):
            # Gradient fill on shape
            fill_code = "// Gradient fill - apply via .fill(gradient)"
            break

    # Avoid double parens: RoundedRectangle already includes ()
    if '(' in shape_name:
        lines.append(f'{prefix}{shape_name}')
    else:
        lines.append(f'{prefix}{shape_name}()')

    # Divider doesn't support fill/stroke
    if shape_name == 'Divider':
        bbox = node.get('absoluteBoundingBox', {})
        w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
        if w and h:
            lines.append(f'{prefix}    .frame(width: {w}, height: {h})')
        for mod in _swiftui_appearance_modifiers(node):
            lines.append(f'{prefix}    {mod}')
        return '\n'.join(lines)

    if fill_code:
        lines.append(f'{prefix}    {fill_code}')

    # Stroke
    stroke_data = parse_stroke(node)
    if stroke_data and stroke_data.get('weight') and stroke_data.get('colors'):
        first_color = stroke_data['colors'][0]
        if first_color.get('type') == 'SOLID':
            hex_c = first_color.get('hex', '#000000')
            rgb = hex_to_rgb(hex_c)
            weight = stroke_data['weight']
            lines.append(f'{prefix}    .stroke(Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f}), lineWidth: {weight})')

    # Frame
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
    if w and h:
        lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Non-uniform corner radius (clip shape)
    corner_radii = parse_corners(node)
    if corner_radii and not corner_radii.get('isUniform'):
        tl = int(corner_radii['topLeft'])
        tr = int(corner_radii['topRight'])
        br = int(corner_radii['bottomRight'])
        bl = int(corner_radii['bottomLeft'])
        lines.append(f'{prefix}    .clipShape(RoundedCorner(topLeft: {tl}, topRight: {tr}, bottomRight: {br}, bottomLeft: {bl}))')

    # Effects & appearance
    for mod in _swiftui_effects_modifier(node):
        lines.append(f'{prefix}    {mod}')
    for mod in _swiftui_appearance_modifiers(node):
        lines.append(f'{prefix}    {mod}')

    return '\n'.join(lines)


def _is_circle(node: Dict[str, Any]) -> bool:
    """Check if ellipse is a perfect circle."""
    bbox = node.get('absoluteBoundingBox', {})
    w = bbox.get('width', 0)
    h = bbox.get('height', 0)
    return abs(w - h) < 1


def _swiftui_vector_node(node: Dict[str, Any], indent: int) -> str:
    """Generate placeholder for vector nodes (icons, custom shapes)."""
    prefix = ' ' * indent
    name = node.get('name', 'vector')
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 24)), int(bbox.get('height', 24))

    # Check if it looks like an icon
    is_icon = w <= 48 and h <= 48
    if is_icon:
        return f'{prefix}Image(systemName: "{name.lower().replace(" ", ".")}") // Replace with actual icon\n{prefix}    .frame(width: {w}, height: {h})'

    return f'{prefix}// Vector: {name}\n{prefix}Rectangle()\n{prefix}    .frame(width: {w}, height: {h})'


# ---------------------------------------------------------------------------
# Task 6: Container node renderer
# ---------------------------------------------------------------------------

def _swiftui_container_node(node: Dict[str, Any], indent: int, depth: int) -> str:
    """Generate SwiftUI container (VStack/HStack/ZStack) with recursive children."""
    prefix = ' ' * indent
    lines = []
    children = node.get('children', [])

    # Determine container type from layout mode
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    primary_align = node.get('primaryAxisAlignItems', 'MIN')
    counter_align = node.get('counterAxisAlignItems', 'MIN')

    if layout_mode == 'VERTICAL':
        container = 'VStack'
        h_align_map = {'MIN': '.leading', 'CENTER': '.center', 'MAX': '.trailing'}
        alignment = h_align_map.get(counter_align, '.center')
    elif layout_mode == 'HORIZONTAL':
        container = 'HStack'
        v_align_map = {'MIN': '.top', 'CENTER': '.center', 'MAX': '.bottom'}
        alignment = v_align_map.get(counter_align, '.center')
    else:
        container = 'ZStack'
        alignment = '.center'

    # Build spacing param
    params = []
    if alignment != '.center' or container != 'ZStack':
        params.append(f"alignment: {alignment}")
    if gap and container != 'ZStack':
        params.append(f"spacing: {int(gap)}")
    params_str = ', '.join(params)

    # If no children, render as styled Rectangle
    if not children:
        return _swiftui_empty_container(node, indent)

    # Open container
    lines.append(f'{prefix}{container}({params_str}) {{')

    # Render children recursively
    child_count = 0
    for child in children:
        if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
            lines.append(f'{prefix}    // ... {len(children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
            break
        if not child.get('visible', True):
            continue
        child_code = _generate_swiftui_node(child, indent + 4, depth + 1)
        if child_code:
            lines.append(child_code)
            child_count += 1

    # Close container
    lines.append(f'{prefix}}}')

    # Collect and apply modifiers
    modifiers, gradient_def = _swiftui_collect_modifiers(node)
    if gradient_def:
        lines.append(gradient_def)
    for mod in modifiers:
        lines.append(f'{prefix}{mod}')

    return '\n'.join(lines)


def _swiftui_empty_container(node: Dict[str, Any], indent: int) -> str:
    """Render a container with no children as a styled shape."""
    prefix = ' ' * indent
    lines = []
    name = node.get('name', 'Unknown')

    # Check for background fill
    fills = node.get('fills', [])
    has_fill = False
    for fill in fills:
        if fill.get('visible', True) and fill.get('type') == 'SOLID':
            color = fill.get('color', {})
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            lines.append(f'{prefix}// {name}')
            if a < 1:
                lines.append(f'{prefix}Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f})')
            else:
                lines.append(f'{prefix}Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f})')
            has_fill = True
            break

    if not has_fill:
        lines.append(f'{prefix}// {name}')
        lines.append(f'{prefix}Color.clear')

    # Frame and other modifiers
    modifiers, _ = _swiftui_collect_modifiers(node)
    for mod in modifiers:
        lines.append(f'{prefix}    {mod}')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Task 7: Public entry point
# ---------------------------------------------------------------------------

def generate_swiftui_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate complete SwiftUI view from Figma node tree.

    Public entry point. Produces a full SwiftUI struct with:
    - Import statement
    - View struct with body
    - Gradient definitions if needed
    - Preview provider
    - RoundedCorner helper shape if needed
    """
    # Generate body content
    body_code = _generate_swiftui_node(node, indent=12, depth=0)
    if not body_code:
        body_code = '            // Empty content'

    # Collect root modifiers
    modifiers, gradient_def = _swiftui_collect_modifiers(node)
    modifiers_str = '\n        '.join(modifiers) if modifiers else ''

    # Determine root container
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    counter_align = node.get('counterAxisAlignItems', 'MIN')

    if layout_mode == 'VERTICAL':
        container = 'VStack'
        h_align_map = {'MIN': '.leading', 'CENTER': '.center', 'MAX': '.trailing'}
        alignment = h_align_map.get(counter_align, '.center')
    elif layout_mode == 'HORIZONTAL':
        container = 'HStack'
        v_align_map = {'MIN': '.top', 'CENTER': '.center', 'MAX': '.bottom'}
        alignment = v_align_map.get(counter_align, '.center')
    else:
        container = 'ZStack'
        alignment = '.center'

    params = []
    if alignment != '.center' or container != 'ZStack':
        params.append(f"alignment: {alignment}")
    if gap and container != 'ZStack':
        params.append(f"spacing: {int(gap)}")
    params_str = ', '.join(params)

    # Check if we need gradient or RoundedCorner definitions
    gradient_section = ''
    if gradient_def:
        gradient_section = f'\n{gradient_def}\n'

    # Build children code directly (not via _swiftui_container_node to avoid double wrapping)
    children = node.get('children', [])
    children_lines = []
    child_count = 0
    for child in children:
        if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
            children_lines.append(f'            // ... {len(children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
            break
        if not child.get('visible', True):
            continue
        child_code = _generate_swiftui_node(child, indent=12, depth=1)
        if child_code:
            children_lines.append(child_code)
            child_count += 1

    children_code = '\n'.join(children_lines) if children_lines else '            // Content'

    code = f'''import SwiftUI

struct {component_name}: View {{{gradient_section}
    var body: some View {{
        {container}({params_str}) {{
{children_code}
        }}
        {modifiers_str}
    }}
}}

#Preview {{
    {component_name}()
}}'''

    # Add RoundedCorner helper if needed in output
    if 'RoundedCorner' in code:
        code += _rounded_corner_shape()

    return code


def _rounded_corner_shape() -> str:
    """Generate the RoundedCorner custom Shape struct."""
    return '''

// Custom shape for individual corner radii
struct RoundedCorner: Shape {
    var topLeft: CGFloat = 0
    var topRight: CGFloat = 0
    var bottomRight: CGFloat = 0
    var bottomLeft: CGFloat = 0

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let w = rect.size.width
        let h = rect.size.height

        path.move(to: CGPoint(x: w / 2, y: 0))
        path.addLine(to: CGPoint(x: w - topRight, y: 0))
        path.addArc(center: CGPoint(x: w - topRight, y: topRight), radius: topRight, startAngle: .degrees(-90), endAngle: .degrees(0), clockwise: false)
        path.addLine(to: CGPoint(x: w, y: h - bottomRight))
        path.addArc(center: CGPoint(x: w - bottomRight, y: h - bottomRight), radius: bottomRight, startAngle: .degrees(0), endAngle: .degrees(90), clockwise: false)
        path.addLine(to: CGPoint(x: bottomLeft, y: h))
        path.addArc(center: CGPoint(x: bottomLeft, y: h - bottomLeft), radius: bottomLeft, startAngle: .degrees(90), endAngle: .degrees(180), clockwise: false)
        path.addLine(to: CGPoint(x: 0, y: topLeft))
        path.addArc(center: CGPoint(x: topLeft, y: topLeft), radius: topLeft, startAngle: .degrees(180), endAngle: .degrees(270), clockwise: false)
        path.closeSubpath()

        return path
    }
}'''
