"""
SwiftUI Code Generator - Recursive rendering with full property support.

Generates production-quality SwiftUI code from Figma node trees.
Supports: fills (solid, gradient, image), strokes, corner radius, shadows,
blur, opacity, blend modes, rotation, padding, auto-layout, text styling.
"""

import re
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
    """Generate SwiftUI background modifier supporting multi-fill and all gradient types.
    Returns (modifier_code, gradient_definitions).
    """
    fill_layers = parse_fills(node)
    if not fill_layers:
        return '', ''

    # Single fill - simple background
    if len(fill_layers) == 1:
        code, grad_def = _fill_layer_to_swiftui(fill_layers[0])
        if code:
            return f'.background({code})', grad_def
        return '', ''

    # Multi-fill - use ZStack layering via .background
    bg_parts = []
    grad_defs = []
    for layer in reversed(fill_layers):  # bottom-to-top in Figma
        code, grad_def = _fill_layer_to_swiftui(layer)
        if code:
            bg_parts.append(code)
            if grad_def:
                grad_defs.append(grad_def)

    if not bg_parts:
        return '', ''

    if len(bg_parts) == 1:
        return f'.background({bg_parts[0]})', '\n'.join(grad_defs)

    # Stack multiple fills
    layers = '\n            '.join(bg_parts)
    modifier = f""".background(
            ZStack {{
                {layers}
            }}
        )"""
    return modifier, '\n'.join(grad_defs)


def _fill_layer_to_swiftui(layer: FillLayer) -> tuple[str, str]:
    """Convert a single FillLayer to SwiftUI code.
    Returns (view_code, gradient_definition).
    """
    if layer.type == 'SOLID' and layer.color:
        c = layer.color
        color_code = f"Color(red: {c.r:.3f}, green: {c.g:.3f}, blue: {c.b:.3f})"
        if c.a < 1:
            color_code += f".opacity({c.a:.2f})"
        return color_code, ''

    elif layer.gradient:
        return _gradient_to_swiftui(layer.gradient)

    elif layer.type == 'IMAGE':
        return 'Color.gray.opacity(0.3) // Image placeholder', ''

    return '', ''


def _gradient_to_swiftui(gradient: GradientDef) -> tuple[str, str]:
    """Convert GradientDef to SwiftUI gradient code.
    Returns (gradient_code, gradient_variable_definition).
    """
    stops_code = []
    for stop in gradient.stops:
        c = stop.color
        color = f"Color(red: {c.r:.3f}, green: {c.g:.3f}, blue: {c.b:.3f})"
        if c.a < 1:
            color += f".opacity({c.a:.2f})"
        stops_code.append(f".init(color: {color}, location: {stop.position:.4f})")

    stops_str = ', '.join(stops_code)

    if gradient.type == 'LINEAR':
        start, end = _gradient_direction_swiftui(gradient.handle_positions)
        code = f"LinearGradient(stops: [{stops_str}], startPoint: {start}, endPoint: {end})"

    elif gradient.type == 'RADIAL':
        code = f"RadialGradient(stops: [{stops_str}], center: .center, startRadius: 0, endRadius: 200)"

    elif gradient.type == 'ANGULAR':
        code = f"AngularGradient(stops: [{stops_str}], center: .center)"

    elif gradient.type == 'DIAMOND':
        # Approximate as radial
        code = f"RadialGradient(stops: [{stops_str}], center: .center, startRadius: 0, endRadius: 200)"

    else:
        return '', ''

    if gradient.opacity < 1:
        code += f".opacity({gradient.opacity:.2f})"

    return code, ''


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
    """Generate stroke modifier supporting solid, gradient, and dashed strokes."""
    stroke = parse_stroke(node)
    if not stroke or stroke.weight == 0:
        return ''

    corners = parse_corners(node)
    cr = corners.uniform_value if corners and corners.is_uniform else 0

    first_color = stroke.colors[0] if stroke.colors else None
    if not first_color:
        return ''

    # Build stroke style (for dashed borders)
    has_dashes = len(stroke.dashes) > 0
    dash_str = ', '.join(str(int(d)) for d in stroke.dashes) if has_dashes else ''

    if first_color.type == 'SOLID' and first_color.color:
        c = first_color.color
        color_code = f"Color(red: {c.r:.3f}, green: {c.g:.3f}, blue: {c.b:.3f})"
        if c.a < 1:
            color_code += f".opacity({c.a:.2f})"

        if has_dashes:
            return (f".overlay(\n"
                    f"            RoundedRectangle(cornerRadius: {cr})\n"
                    f"                .stroke(style: StrokeStyle(lineWidth: {stroke.weight}, dash: [{dash_str}]))\n"
                    f"                .foregroundColor({color_code})\n"
                    f"        )")

        return (f".overlay(\n"
                f"            RoundedRectangle(cornerRadius: {cr})\n"
                f"                .stroke({color_code}, lineWidth: {stroke.weight})\n"
                f"        )")

    elif first_color.gradient:
        grad_code, _ = _gradient_to_swiftui(first_color.gradient)
        if not grad_code:
            return ''

        if has_dashes:
            return (f".overlay(\n"
                    f"            RoundedRectangle(cornerRadius: {cr})\n"
                    f"                .stroke(style: StrokeStyle(lineWidth: {stroke.weight}, dash: [{dash_str}]))\n"
                    f"                .foregroundStyle({grad_code})\n"
                    f"        )")

        return (f".overlay(\n"
                f"            RoundedRectangle(cornerRadius: {cr})\n"
                f"                .stroke({grad_code}, lineWidth: {stroke.weight})\n"
                f"        )")

    return ''


def _swiftui_corner_modifier(node: Dict[str, Any]) -> str:
    """Generate SwiftUI corner radius modifier."""
    radii = parse_corners(node)
    if not radii:
        return ''

    if radii.is_uniform:
        tl = radii.top_left
        if tl > 0:
            return f".cornerRadius({int(tl)})"
        return ''
    else:
        tl = int(radii.top_left)
        tr = int(radii.top_right)
        br = int(radii.bottom_right)
        bl = int(radii.bottom_left)
        return f".clipShape(RoundedCorner(topLeft: {tl}, topRight: {tr}, bottomRight: {br}, bottomLeft: {bl}))"


def _swiftui_effects_modifier(node: Dict[str, Any]) -> list[str]:
    """Generate shadow and blur effect modifiers including background blur."""
    shadows, blurs = parse_effects(node)
    modifiers = []

    for shadow in shadows:
        c = shadow.color
        r, g, b = c.rgb_ints
        if shadow.type == 'DROP_SHADOW':
            modifiers.append(
                f".shadow(color: Color(red: {r/255:.3f}, green: {g/255:.3f}, blue: {b/255:.3f}).opacity({c.a:.2f}), "
                f"radius: {int(shadow.radius)}, x: {int(shadow.offset_x)}, y: {int(shadow.offset_y)})"
            )
        elif shadow.type == 'INNER_SHADOW':
            # Inner shadow approximation using overlay
            modifiers.append(
                f".overlay(\n"
                f"            RoundedRectangle(cornerRadius: 0)\n"
                f"                .stroke(Color(red: {r/255:.3f}, green: {g/255:.3f}, blue: {b/255:.3f}).opacity({c.a:.2f}), lineWidth: {int(shadow.radius)})\n"
                f"                .blur(radius: {int(shadow.radius)})\n"
                f"                .clipShape(RoundedRectangle(cornerRadius: 0))\n"
                f"        )"
            )

    for blur in blurs:
        if blur.type == 'LAYER_BLUR':
            modifiers.append(f".blur(radius: {int(blur.radius)})")
        elif blur.type == 'BACKGROUND_BLUR':
            modifiers.append(".background(.ultraThinMaterial)")

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
    """Generate SwiftUI Text view with full styling including gradient text."""
    prefix = ' ' * indent
    lines = []

    text = node.get('characters', node.get('name', ''))
    ts = parse_text_style(node)

    # Hyperlink
    hyperlink = node.get('hyperlink')
    hyperlink_url = None
    if hyperlink and hyperlink.get('type') == 'URL':
        hyperlink_url = hyperlink.get('url', '')

    # Escape text
    escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    weight = SWIFTUI_WEIGHT_MAP.get(ts.font_weight, '.regular')

    # Text or Link
    if hyperlink_url:
        lines.append(f'{prefix}Link("{escaped_text}", destination: URL(string: "{hyperlink_url}")!)')
    else:
        lines.append(f'{prefix}Text("{escaped_text}")')

    # Font
    if ts.font_family:
        lines.append(f'{prefix}    .font(.custom("{ts.font_family}", size: {ts.font_size}))')
        lines.append(f'{prefix}    .fontWeight({weight})')
    else:
        lines.append(f'{prefix}    .font(.system(size: {ts.font_size}, weight: {weight}))')

    # Text color or gradient
    if ts.gradient:
        grad_code, _ = _gradient_to_swiftui(ts.gradient)
        if grad_code:
            lines.append(f'{prefix}    .foregroundStyle({grad_code})')
    elif ts.color:
        c = ts.color
        color_code = f"Color(red: {c.r:.3f}, green: {c.g:.3f}, blue: {c.b:.3f})"
        if c.a < 1:
            lines.append(f'{prefix}    .foregroundColor({color_code}.opacity({c.a:.2f}))')
        else:
            lines.append(f'{prefix}    .foregroundColor({color_code})')

    # Line height (approximated via lineSpacing)
    if ts.line_height and ts.line_height > ts.font_size:
        spacing = ts.line_height - ts.font_size
        lines.append(f'{prefix}    .lineSpacing({spacing:.0f})')

    # Letter spacing
    if ts.letter_spacing:
        lines.append(f'{prefix}    .tracking({ts.letter_spacing:.1f})')

    # Text alignment
    align_map = {'LEFT': '.leading', 'CENTER': '.center', 'RIGHT': '.trailing'}
    if ts.text_align in align_map and ts.text_align != 'LEFT':
        lines.append(f'{prefix}    .multilineTextAlignment({align_map[ts.text_align]})')

    # Text case
    if ts.text_case == 'UPPER':
        lines.append(f'{prefix}    .textCase(.uppercase)')
    elif ts.text_case == 'LOWER':
        lines.append(f'{prefix}    .textCase(.lowercase)')

    # Text decoration
    if ts.text_decoration == 'UNDERLINE':
        lines.append(f'{prefix}    .underline()')
    elif ts.text_decoration == 'STRIKETHROUGH':
        lines.append(f'{prefix}    .strikethrough()')

    # Max lines / truncation
    if ts.max_lines:
        lines.append(f'{prefix}    .lineLimit({ts.max_lines})')
        if ts.truncation == 'ENDING':
            lines.append(f'{prefix}    .truncationMode(.tail)')

    # Frame (width constraint if needed)
    bbox = node.get('absoluteBoundingBox', {})
    w = int(bbox.get('width', 0))
    if w > 0:
        lines.append(f'{prefix}    .frame(width: {w}, alignment: {align_map.get(ts.text_align, ".leading")})')

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
        if corner_radii and corner_radii.is_uniform and corner_radii.top_left > 0:
            shape_name = f"RoundedRectangle(cornerRadius: {int(corner_radii.top_left)})"
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
    if stroke_data and stroke_data.weight and stroke_data.colors:
        first_color = stroke_data.colors[0]
        if first_color.type == 'SOLID' and first_color.color:
            hex_c = first_color.color.hex
            rgb = hex_to_rgb(hex_c)
            weight = stroke_data.weight
            lines.append(f'{prefix}    .stroke(Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f}), lineWidth: {weight})')

    # Frame
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
    if w and h:
        lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Non-uniform corner radius (clip shape)
    corner_radii = parse_corners(node)
    if corner_radii and not corner_radii.is_uniform:
        tl = int(corner_radii.top_left)
        tr = int(corner_radii.top_right)
        br = int(corner_radii.bottom_right)
        bl = int(corner_radii.bottom_left)
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

    # Filter visible children for SPACE_BETWEEN logic
    visible_children = [c for c in children if c.get('visible', True)]

    # Render children recursively
    child_count = 0
    for i, child in enumerate(visible_children):
        if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
            lines.append(f'{prefix}    // ... {len(visible_children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
            break
        child_code = _generate_swiftui_node(child, indent + 4, depth + 1)
        if child_code:
            lines.append(child_code)
            child_count += 1
            if primary_align == 'SPACE_BETWEEN' and i < len(visible_children) - 1:
                lines.append(f'{prefix}    Spacer()')

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
# Component name sanitizer
# ---------------------------------------------------------------------------

def _sanitize_component_name(name: str) -> str:
    """Convert Figma frame name to valid SwiftUI struct name.
    'iPhone 13 & 14 - 241' -> 'Screen241'
    'Effects screen' -> 'EffectsScreen'
    'Login Page' -> 'LoginPage'
    """
    # Remove device names
    cleaned = re.sub(r'(?i)iphone\s*\d+\s*[&/,]*\s*\d*\s*[-\u2013]\s*', '', name)
    cleaned = re.sub(r'(?i)ipad\s*\w*\s*[-\u2013]\s*', '', cleaned)
    cleaned = re.sub(r'(?i)android\s*\w*\s*[-\u2013]\s*', '', cleaned)
    cleaned = cleaned.strip(' -\u2013')

    if not cleaned:
        cleaned = name  # Fallback to original

    # PascalCase conversion
    words = re.split(r'[\s_\-\u2013/&]+', cleaned)
    pascal = ''.join(w.capitalize() for w in words if w)

    # Remove non-alphanumeric chars
    pascal = re.sub(r'[^a-zA-Z0-9]', '', pascal)

    # Ensure starts with letter
    if pascal and not pascal[0].isalpha():
        pascal = 'Screen' + pascal

    return pascal or 'GeneratedView'


# ---------------------------------------------------------------------------
# Task 7: Public entry point
# ---------------------------------------------------------------------------

def generate_swiftui_code(node: Dict[str, Any], component_name: str = '') -> str:
    """Generate complete SwiftUI view from Figma node tree.

    Public entry point. Produces a full SwiftUI struct with:
    - Import statement
    - View struct with body
    - Gradient definitions if needed
    - Preview provider
    - RoundedCorner helper shape if needed
    """
    if not component_name:
        component_name = _sanitize_component_name(node.get('name', 'GeneratedView'))

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
