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
    sanitize_component_name, map_icon_name,
)



# ---------------------------------------------------------------------------
# Task 2: Recursive node dispatcher
# ---------------------------------------------------------------------------

def _generate_swiftui_node(node: Dict[str, Any], indent: int = 8, depth: int = 0, parent_node: Dict[str, Any] = None) -> str:
    """Recursively generate SwiftUI code for a single node with full property support."""
    if depth > MAX_DEPTH:
        prefix = ' ' * indent
        name = node.get('name', 'Unknown')
        return f'{prefix}// Depth limit reached: {name}'

    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')
    prefix = ' ' * indent

    if node_type == 'TEXT':
        return _swiftui_text_node(node, indent, parent_node)
    elif node_type in ('RECTANGLE', 'ELLIPSE', 'LINE', 'STAR', 'REGULAR_POLYGON'):
        return _swiftui_shape_node(node, indent)
    elif node_type in ('VECTOR', 'BOOLEAN_OPERATION'):
        return _swiftui_vector_node(node, indent)
    elif node_type in ('FRAME', 'GROUP', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE', 'SECTION'):
        return _swiftui_container_node(node, indent, depth, parent_node)
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

    # Get node dimensions for gradient sizing
    bbox = node.get('absoluteBoundingBox', {})
    node_width = bbox.get('width', 0)
    node_height = bbox.get('height', 0)

    # Single fill - simple background
    if len(fill_layers) == 1:
        code, grad_def = _fill_layer_to_swiftui(fill_layers[0], node_width, node_height)
        if code:
            return f'.background({code})', grad_def
        return '', ''

    # Multi-fill - use ZStack layering via .background
    bg_parts = []
    grad_defs = []
    for layer in fill_layers:  # Figma fills are bottom-to-top; ZStack renders last-on-top
        code, grad_def = _fill_layer_to_swiftui(layer, node_width, node_height)
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


def _fill_layer_to_swiftui(layer: FillLayer, node_width: float = 0, node_height: float = 0) -> tuple[str, str]:
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
        return _gradient_to_swiftui(layer.gradient, node_width, node_height)

    elif layer.type == 'IMAGE':
        return 'Color.gray.opacity(0.3) // Image placeholder', ''

    return '', ''


def _gradient_to_swiftui(gradient: GradientDef, node_width: float = 0, node_height: float = 0) -> tuple[str, str]:
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
        end_radius = int(max(node_width, node_height) / 2) if (node_width and node_height) else 200
        code = f"RadialGradient(stops: [{stops_str}], center: .center, startRadius: 0, endRadius: {end_radius})"

    elif gradient.type == 'ANGULAR':
        code = f"AngularGradient(stops: [{stops_str}], center: .center)"

    elif gradient.type == 'DIAMOND':
        # Approximate as radial
        end_radius = int(max(node_width, node_height) / 2) if (node_width and node_height) else 200
        code = f"RadialGradient(stops: [{stops_str}], center: .center, startRadius: 0, endRadius: {end_radius})"

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
                    f"                .stroke({color_code}, style: StrokeStyle(lineWidth: {stroke.weight}, dash: [{dash_str}]))\n"
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
                    f"                .stroke({grad_code}, style: StrokeStyle(lineWidth: {stroke.weight}, dash: [{dash_str}]))\n"
                    f"        )")

        return (f".overlay(\n"
                f"            RoundedRectangle(cornerRadius: {cr})\n"
                f"                .stroke({grad_code}, style: StrokeStyle(lineWidth: {stroke.weight}))\n"
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
        # Skip if all corners are 0
        if tl == 0 and tr == 0 and br == 0 and bl == 0:
            return ''
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

    # Padding BEFORE frame for auto-layout nodes (Figma padding = inside content area)
    has_auto_layout = node.get('layoutMode') in ('VERTICAL', 'HORIZONTAL')
    padding_mod = None
    pt = node.get('paddingTop', 0)
    pr = node.get('paddingRight', 0)
    pb = node.get('paddingBottom', 0)
    pl = node.get('paddingLeft', 0)
    if pt or pr or pb or pl:
        if pt == pr == pb == pl and pt > 0:
            padding_mod = f".padding({int(pt)})"
        else:
            padding_mod = f".padding(EdgeInsets(top: {int(pt)}, leading: {int(pl)}, bottom: {int(pb)}, trailing: {int(pr)}))"

    # For auto-layout: padding → frame → background (padding is inside)
    if has_auto_layout and padding_mod:
        modifiers.append(padding_mod)

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

    # For non-auto-layout: padding after everything else
    if not has_auto_layout and padding_mod:
        modifiers.append(padding_mod)

    # Clip content
    if node.get('clipsContent', False):
        modifiers.append(".clipped()")

    return modifiers, gradient_def


# ---------------------------------------------------------------------------
# Task 4: Text node renderer
# ---------------------------------------------------------------------------

def _build_attributed_text(text: str, overrides: list, table: dict, base_ts, prefix: str) -> str:
    """Build concatenated Text() expressions for mixed bold/regular spans."""
    if not text or not overrides:
        return ''

    # Build segments: group consecutive characters with the same style override
    segments = []
    current_style = overrides[0] if overrides else 0
    current_start = 0

    # Pad overrides to text length (remaining chars use style 0 = base style)
    padded = list(overrides) + [0] * (len(text) - len(overrides))

    for i in range(1, len(text)):
        if padded[i] != current_style:
            segments.append((text[current_start:i], current_style))
            current_style = padded[i]
            current_start = i
    segments.append((text[current_start:], current_style))

    if len(segments) <= 1:
        return ''  # No mixed styles

    # Determine which style IDs are bold
    base_weight = base_ts.font_weight or 400
    bold_styles = set()
    for style_id, style_props in table.items():
        style_weight = style_props.get('fontWeight', base_weight)
        if style_weight >= 600:  # semibold or bolder
            bold_styles.add(int(style_id))

    # Build Text concatenation
    parts = []
    for seg_text, style_id in segments:
        escaped = seg_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        if int(style_id) in bold_styles:
            parts.append(f'Text("{escaped}").bold()')
        else:
            parts.append(f'Text("{escaped}")')

    return f'{prefix}({" + ".join(parts)})'


def _swiftui_text_node(node: Dict[str, Any], indent: int, parent_node: Dict[str, Any] = None) -> str:
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

    weight = SWIFTUI_WEIGHT_MAP.get(ts.font_weight, '.regular')

    # Check for attributed text (mixed bold/regular spans)
    style_overrides = node.get('characterStyleOverrides', [])
    style_override_table = node.get('styleOverrideTable', {})
    has_mixed_styles = bool(style_overrides and style_override_table and
                           any(v != style_overrides[0] for v in style_overrides))

    if has_mixed_styles and not hyperlink_url:
        # Build concatenated Text() with mixed styles
        attributed_code = _build_attributed_text(text, style_overrides, style_override_table, ts, prefix)
        if attributed_code:
            lines.append(attributed_code)
            # Font base (applied to the whole group)
            if ts.font_family:
                lines.append(f'{prefix}    .font(.custom("{ts.font_family}", size: {ts.font_size}))')
            else:
                lines.append(f'{prefix}    .font(.system(size: {ts.font_size}, weight: {weight}))')
        else:
            # Fallback to simple text
            has_mixed_styles = False

    if not has_mixed_styles or hyperlink_url:
        # Escape text
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

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
    parent_is_space_between = (parent_node and
        parent_node.get('primaryAxisAlignItems') == 'SPACE_BETWEEN')
    # Check if parent is left-aligned auto-layout
    parent_counter_align = parent_node.get('counterAxisAlignItems', 'MIN') if parent_node else 'MIN'
    parent_layout = parent_node.get('layoutMode') if parent_node else None
    if w > 0:
        frame_align = align_map.get(ts.text_align, '.leading')
        # SPACE_BETWEEN parent or CENTER-aligned text in auto-layout:
        # Use the text node's own textAlignHorizontal for alignment
        if parent_is_space_between or ts.text_align == 'CENTER':
            # Use text's own alignment, not parent's
            text_frame_align = align_map.get(ts.text_align, '.leading')
            # In auto-layout, CENTER usually means "fill width" not "centered text"
            if parent_layout and ts.text_align == 'CENTER':
                text_frame_align = '.leading'
            lines.append(f'{prefix}    .frame(maxWidth: .infinity, alignment: {text_frame_align})')
        elif '\n' not in text and w < 200:
            # Short single-line text: don't constrain width, let parent layout handle it
            pass
        else:
            lines.append(f'{prefix}    .frame(width: {w}, alignment: {frame_align})')

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
        # Check arcData for ring/donut shapes (innerRadius > 0)
        arc_data = node.get('arcData', {})
        inner_radius = arc_data.get('innerRadius', 0)
        if inner_radius > 0:
            return _swiftui_ellipse_ring(node, indent)
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

    # Fill - check for IMAGE fill first (renders as Image instead of shape)
    fills = node.get('fills', [])
    has_image_fill = False
    fill_code = ''
    for fill in fills:
        if not fill.get('visible', True):
            continue
        if fill.get('type') == 'IMAGE':
            has_image_fill = True
            break
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
            # Generate actual gradient fill code
            fill_layers = parse_fills(node)
            for layer in fill_layers:
                if layer.gradient:
                    grad_code, _ = _gradient_to_swiftui(layer.gradient)
                    if grad_code:
                        fill_code = f".fill({grad_code})"
                    break
            if not fill_code:
                fill_code = "// Gradient fill"
            break

    # If IMAGE fill, render as Image placeholder instead of shape
    if has_image_fill:
        name = node.get('name', 'image')
        bbox = node.get('absoluteBoundingBox', {})
        w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
        lines.append(f'{prefix}Image(systemName: "photo") // {name}')
        lines.append(f'{prefix}    .resizable()')
        lines.append(f'{prefix}    .scaledToFill()')
        if w and h:
            lines.append(f'{prefix}    .frame(width: {w}, height: {h})')
        corner_radii = parse_corners(node)
        if corner_radii and corner_radii.is_uniform and corner_radii.top_left > 0:
            lines.append(f'{prefix}    .clipShape(RoundedRectangle(cornerRadius: {int(corner_radii.top_left)}))')
        else:
            lines.append(f'{prefix}    .clipped()')
        # Stroke
        stroke_mod = _swiftui_stroke_modifier(node)
        if stroke_mod:
            lines.append(f'{prefix}    {stroke_mod}')
        # Effects & appearance
        for mod in _swiftui_effects_modifier(node):
            lines.append(f'{prefix}    {mod}')
        for mod in _swiftui_appearance_modifiers(node):
            lines.append(f'{prefix}    {mod}')
        return '\n'.join(lines)

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

    # Stroke (supports solid, gradient, and dashed borders)
    stroke_mod = _swiftui_stroke_modifier(node)
    if stroke_mod:
        lines.append(f'{prefix}    {stroke_mod}')

    # Frame
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
    if w and h:
        lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Non-uniform corner radius (clip shape) - skip if all corners are 0
    corner_radii = parse_corners(node)
    if corner_radii and not corner_radii.is_uniform:
        tl = int(corner_radii.top_left)
        tr = int(corner_radii.top_right)
        br = int(corner_radii.bottom_right)
        bl = int(corner_radii.bottom_left)
        if tl > 0 or tr > 0 or br > 0 or bl > 0:
            lines.append(f'{prefix}    .clipShape(RoundedCorner(topLeft: {tl}, topRight: {tr}, bottomRight: {br}, bottomLeft: {bl}))')

    # Effects & appearance
    for mod in _swiftui_effects_modifier(node):
        lines.append(f'{prefix}    {mod}')
    for mod in _swiftui_appearance_modifiers(node):
        lines.append(f'{prefix}    {mod}')

    return '\n'.join(lines)


def _swiftui_ellipse_ring(node: Dict[str, Any], indent: int) -> str:
    """Generate SwiftUI Circle().stroke() for ring/donut ELLIPSE nodes (innerRadius > 0)."""
    prefix = ' ' * indent
    lines = []
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
    arc_data = node.get('arcData', {})
    inner_radius = arc_data.get('innerRadius', 0.5)

    # Calculate stroke lineWidth from inner radius ratio
    # innerRadius is 0-1 ratio: 0 = solid fill, 1 = infinitely thin ring
    # lineWidth = diameter * (1 - innerRadius) / 2
    diameter = max(w, h)
    line_width = max(1, int(diameter * (1 - inner_radius) / 2))

    # Fill color for the stroke
    fills = node.get('fills', [])
    color_code = 'Color.primary'
    for fill in fills:
        if not fill.get('visible', True):
            continue
        if fill.get('type') == 'SOLID':
            color = fill.get('color', {})
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            if a < 1:
                color_code = f"Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f})"
            else:
                color_code = f"Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f})"
            break

    # Trim for partial arcs
    import math
    TWO_PI = 2 * math.pi
    start_angle = arc_data.get('startingAngle', 0)
    ending_angle = arc_data.get('endingAngle', TWO_PI)

    # Normalize angles to 0..2π range
    norm_start = start_angle % TWO_PI
    norm_end = ending_angle % TWO_PI
    # Calculate arc span
    arc_span = (ending_angle - start_angle) % TWO_PI
    is_full_circle = arc_span < 0.01 or abs(arc_span - TWO_PI) < 0.01

    lines.append(f'{prefix}Circle()')

    # trim() MUST come before stroke() - trim works on Shape, stroke returns View
    if not is_full_circle:
        from_val = max(0, norm_start / TWO_PI)
        to_val = max(from_val + 0.001, (norm_start + arc_span) / TWO_PI)
        lines.append(f'{prefix}    .trim(from: {from_val:.3f}, to: {to_val:.3f})')

    lines.append(f'{prefix}    .stroke({color_code}, lineWidth: {line_width})')

    if w and h:
        lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Figma starts arcs at 12 o'clock, SwiftUI at 3 o'clock → rotate -90°
    if not is_full_circle:
        lines.append(f'{prefix}    .rotationEffect(.degrees(-90))')

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
    """Generate vector nodes: icons, dividers, overlays with fill+opacity support."""
    prefix = ' ' * indent
    name = node.get('name', 'vector')
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 24)), int(bbox.get('height', 24))

    # Parse fill for the vector node
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
            fill_layers = parse_fills(node)
            for layer in fill_layers:
                if layer.gradient:
                    grad_code, _ = _gradient_to_swiftui(layer.gradient)
                    if grad_code:
                        fill_code = f".fill({grad_code})"
                    break
            break

    # Handle divider/line vectors (0-width or 0-height)
    if w == 0 or h == 0:
        stroke_weight = node.get('strokeWeight', 1)
        stroke_color = ''
        for s in node.get('strokes', []):
            if not s.get('visible', True):
                continue
            if s.get('type') == 'SOLID':
                sc = s.get('color', {})
                sr, sg, sb = sc.get('r', 1), sc.get('g', 1), sc.get('b', 1)
                sa = s.get('opacity', sc.get('a', 1))
                if sa < 1:
                    stroke_color = f"Color(red: {sr:.3f}, green: {sg:.3f}, blue: {sb:.3f}).opacity({sa:.2f})"
                else:
                    stroke_color = f"Color(red: {sr:.3f}, green: {sg:.3f}, blue: {sb:.3f})"
                break
        if not stroke_color:
            stroke_color = fill_code.replace('.fill(', '').rstrip(')') if fill_code else 'Color.white.opacity(0.20)'
        sw = int(stroke_weight) if stroke_weight else 1
        if w == 0:
            # Vertical divider
            return f'{prefix}Rectangle()\n{prefix}    .fill({stroke_color})\n{prefix}    .frame(width: {max(sw, 1)}, height: {h})'
        else:
            # Horizontal divider
            return f'{prefix}Rectangle()\n{prefix}    .fill({stroke_color})\n{prefix}    .frame(width: {w}, height: {max(sw, 1)})'

    # Check if it looks like an icon (small size)
    is_icon = w <= 48 and h <= 48
    if is_icon:
        sf_symbol = map_icon_name(name)
        return f'{prefix}Image(systemName: "{sf_symbol}") // {name}\n{prefix}    .frame(width: {w}, height: {h})'

    # Large vector with fill (e.g., overlay rectangle)
    lines = []
    lines.append(f'{prefix}Rectangle()')
    if fill_code:
        lines.append(f'{prefix}    {fill_code}')
    lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Opacity
    opacity = node.get('opacity', 1)
    if opacity < 1:
        lines.append(f'{prefix}    .opacity({opacity:.2f})')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Task 6: Container node renderer
# ---------------------------------------------------------------------------

def _analyze_children_layout(children: list, container_bbox: dict) -> tuple:
    """Analyze children positions to determine best container type.
    Returns (container_type, estimated_spacing).
    container_type: 'VStack', 'HStack', or 'ZStack'
    """
    visible = [c for c in children if c.get('visible', True) and c.get('absoluteBoundingBox')]
    if len(visible) <= 1:
        return 'ZStack', 0

    # Sort by Y position
    sorted_by_y = sorted(visible, key=lambda c: c['absoluteBoundingBox'].get('y', 0))
    # Sort by X position
    sorted_by_x = sorted(visible, key=lambda c: c['absoluteBoundingBox'].get('x', 0))

    # Check Y-axis sequential (no overlap)
    y_sequential = True
    y_gaps = []
    for i in range(len(sorted_by_y) - 1):
        cur = sorted_by_y[i]['absoluteBoundingBox']
        nxt = sorted_by_y[i + 1]['absoluteBoundingBox']
        cur_bottom = cur.get('y', 0) + cur.get('height', 0)
        nxt_top = nxt.get('y', 0)
        if cur_bottom > nxt_top + 1:  # 1px tolerance
            y_sequential = False
            break
        y_gaps.append(max(0, nxt_top - cur_bottom))

    if y_sequential and len(sorted_by_y) > 1:
        avg_gap = sum(y_gaps) / len(y_gaps) if y_gaps else 0
        return 'VStack', round(avg_gap)

    # Check X-axis sequential (no overlap)
    x_sequential = True
    x_gaps = []
    for i in range(len(sorted_by_x) - 1):
        cur = sorted_by_x[i]['absoluteBoundingBox']
        nxt = sorted_by_x[i + 1]['absoluteBoundingBox']
        cur_right = cur.get('x', 0) + cur.get('width', 0)
        nxt_left = nxt.get('x', 0)
        if cur_right > nxt_left + 1:
            x_sequential = False
            break
        x_gaps.append(max(0, nxt_left - cur_right))

    if x_sequential and len(sorted_by_x) > 1:
        avg_gap = sum(x_gaps) / len(x_gaps) if x_gaps else 0
        return 'HStack', round(avg_gap)

    return 'ZStack', 0


def _is_icon_container(node: Dict[str, Any]) -> bool:
    """Check if a container node is likely an icon frame."""
    children = node.get('children', [])

    # If any child is TEXT, this is NOT just an icon (e.g., PRO badge)
    if any(c.get('type') == 'TEXT' for c in children):
        return False

    name = node.get('name', '')
    bbox = node.get('absoluteBoundingBox', {})
    w = bbox.get('width', 0)
    h = bbox.get('height', 0)
    if w == 0 or h == 0:
        return False

    # Icon library pattern (e.g., "solar:settings-linear", "mdi:heart")
    has_icon_pattern = ':' in name or '/' in name

    # Icon size: small, roughly square
    is_icon_size = 4 <= min(w, h) and max(w, h) <= 128 and max(w, h) / max(min(w, h), 1) <= 2.0

    # All children are vectors/groups (no frames, no text) - catches nested vector groups
    # Note: ELLIPSE excluded - small frames with single ELLIPSE child are bullet points, not icons
    vector_types = {'VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'POLYGON', 'LINE', 'REGULAR_POLYGON', 'GROUP'}
    all_vector_children = children and all(c.get('type') in vector_types for c in children)

    # Export settings hint from Figma
    has_export = bool(node.get('exportSettings'))

    return has_icon_pattern or (is_icon_size and (all_vector_children or has_export))


def _resolve_icon_name(node: Dict[str, Any]) -> str:
    """Resolve the actual icon name from a container, checking children for overrides."""
    name = node.get('name', 'icon')
    children = node.get('children', [])

    # Check children for icon-pattern names (override resolution)
    for child in children:
        child_name = child.get('name', '')
        if ':' in child_name or '/' in child_name:
            return child_name
        # Recurse one level into child groups
        for grandchild in child.get('children', []):
            gc_name = grandchild.get('name', '')
            if ':' in gc_name or '/' in gc_name:
                return gc_name

    return name


def _check_node_flipped(node: Dict[str, Any]) -> bool:
    """Check if a single node has horizontal flip via relativeTransform or absoluteTransform."""
    # Check explicit flip flags (set by _extract_transform)
    transform_info = node.get('transform', {})
    if transform_info.get('flippedHorizontally'):
        return True

    # Check relativeTransform: [[scaleX, skewX, tx], [skewY, scaleY, ty]]
    transform = node.get('relativeTransform')
    # Also check under bounds (figma_get_node_details stores it there)
    if not transform:
        transform = (node.get('bounds') or {}).get('relativeTransform')
    if transform:
        try:
            scale_x = float(transform[0][0])
            if scale_x < 0:
                return True
        except (IndexError, TypeError, ValueError):
            pass
    # Check absoluteTransform as fallback
    abs_transform = node.get('absoluteTransform')
    if abs_transform:
        try:
            scale_x = float(abs_transform[0][0])
            if scale_x < 0:
                return True
        except (IndexError, TypeError, ValueError):
            pass
    # Check rotation - Figma stores rotation in radians
    # ±180° (±π) flips direction; threshold is π/2 (90°)
    rotation = node.get('rotation', 0)
    try:
        if abs(float(rotation)) > 1.5708:  # π/2 radians = 90 degrees
            return True
    except (TypeError, ValueError):
        pass
    return False


def _icon_needs_flip(node: Dict[str, Any], icon_name: str, parent_node: Dict[str, Any] = None) -> bool:
    """Check if icon should be flipped based on transform.

    Checks node itself, parent, children, and grandchildren because
    the flip may be applied at any level in the Figma hierarchy.
    """
    # Check parent node first (designer may flip the wrapper frame, not the icon itself)
    if parent_node and _check_node_flipped(parent_node):
        return True
    # Check this node
    if _check_node_flipped(node):
        return True
    # Check children (flip may be on inner vector/group)
    for child in node.get('children', []):
        if _check_node_flipped(child):
            return True
        # One more level deep
        for grandchild in child.get('children', []):
            if _check_node_flipped(grandchild):
                return True
    return False


def _swiftui_container_node(node: Dict[str, Any], indent: int, depth: int, parent_node: Dict[str, Any] = None) -> str:
    """Generate SwiftUI container (VStack/HStack/ZStack) with recursive children."""
    prefix = ' ' * indent
    lines = []
    children = node.get('children', [])

    # If this container is an icon frame, render as Image with container styling
    if _is_icon_container(node):
        icon_name = _resolve_icon_name(node)
        sf_symbol = map_icon_name(icon_name)

        # Check for icon flip/direction (also check parent - flip may be on wrapper frame)
        if _icon_needs_flip(node, sf_symbol, parent_node=parent_node):
            # Flip arrow direction
            flip_map = {
                'chevron.right': 'chevron.left', 'chevron.left': 'chevron.right',
                'arrow.right': 'arrow.left', 'arrow.left': 'arrow.right',
                'arrowshape.right': 'arrowshape.left', 'arrowshape.left': 'arrowshape.right',
            }
            sf_symbol = flip_map.get(sf_symbol, sf_symbol)

        bbox = node.get('absoluteBoundingBox', {})
        w, h = int(bbox.get('width', 24)), int(bbox.get('height', 24))

        # Check if container has styling (background, cornerRadius)
        has_fills = any(f.get('visible', True) and f.get('type') == 'SOLID' for f in node.get('fills', []))
        corner_radii = parse_corners(node)
        has_styling = has_fills or (corner_radii and corner_radii.top_left > 0)

        if has_styling:
            # Render with container: ZStack { Image }.frame().background().cornerRadius()
            icon_lines = []
            # Determine inner icon size from children
            inner_w, inner_h = w, h
            for child in node.get('children', []):
                cb = child.get('absoluteBoundingBox', {})
                cw, ch = int(cb.get('width', 0)), int(cb.get('height', 0))
                if 0 < cw < w and 0 < ch < h:
                    inner_w, inner_h = cw, ch
                    break

            icon_lines.append(f'{prefix}ZStack {{')
            icon_lines.append(f'{prefix}    Image(systemName: "{sf_symbol}") // {icon_name}')
            icon_lines.append(f'{prefix}        .frame(width: {inner_w}, height: {inner_h})')
            icon_lines.append(f'{prefix}}}')
            icon_lines.append(f'{prefix}.frame(width: {w}, height: {h})')

            # Background color
            for fill in node.get('fills', []):
                if not fill.get('visible', True):
                    continue
                if fill.get('type') == 'SOLID':
                    color = fill.get('color', {})
                    r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
                    a = fill.get('opacity', color.get('a', 1))
                    if a < 1:
                        icon_lines.append(f'{prefix}.background(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}).opacity({a:.2f}))')
                    else:
                        icon_lines.append(f'{prefix}.background(Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}))')
                    break

            # Corner radius
            if corner_radii:
                if corner_radii.is_uniform and corner_radii.top_left > 0:
                    icon_lines.append(f'{prefix}.cornerRadius({int(corner_radii.top_left)})')

            return '\n'.join(icon_lines)
        else:
            return f'{prefix}Image(systemName: "{sf_symbol}") // {icon_name}\n{prefix}    .frame(width: {w}, height: {h})'

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
        # Smart heuristic: analyze children positions to pick VStack/HStack/ZStack
        container_bbox = node.get('absoluteBoundingBox', {})
        container, inferred_gap = _analyze_children_layout(children, container_bbox)
        if container == 'VStack':
            alignment = '.leading'
            gap = inferred_gap
        elif container == 'HStack':
            alignment = '.center'
            gap = inferred_gap
        else:
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

    # Filter visible children for SPACE_BETWEEN logic
    visible_children = [c for c in children if c.get('visible', True)]

    # Single-child frame flatten: if container has exactly 1 visible child and
    # the child is also a container with similar dimensions, skip the wrapper
    if len(visible_children) == 1 and layout_mode:
        child = visible_children[0]
        child_type = child.get('type', '')
        if child_type in ('FRAME', 'GROUP', 'COMPONENT', 'INSTANCE'):
            child_bbox = child.get('absoluteBoundingBox', {})
            node_bbox = node.get('absoluteBoundingBox', {})
            cw = child_bbox.get('width', 0)
            ch = child_bbox.get('height', 0)
            nw = node_bbox.get('width', 0)
            nh = node_bbox.get('height', 0)
            # Same dimensions = redundant wrapper
            if nw > 0 and abs(cw - nw) < 2 and abs(ch - nh) < 2:
                child_code = _generate_swiftui_node(child, indent, depth + 1, parent_node=node)
                if child_code:
                    # Apply this node's modifiers to the child
                    modifiers, gradient_def = _swiftui_collect_modifiers(node)
                    if gradient_def:
                        child_code += '\n' + gradient_def
                    for mod in modifiers:
                        child_code += f'\n{prefix}{mod}'
                    return child_code

    # Detect layout wrap (flex-wrap: wrap) → LazyVGrid with adaptive columns
    layout_wrap = node.get('layoutWrap', 'NO_WRAP')
    needs_wrap = (layout_wrap == 'WRAP' and container == 'HStack')

    # Detect horizontal overflow → wrap in ScrollView(.horizontal)
    # Key insight: Figma's absoluteBoundingBox for auto-layout HStack = full content width,
    # not the clipped/visible width. Compare against parent's width or self clipsContent.
    needs_scroll = False
    if not needs_wrap and container == 'HStack' and len(visible_children) > 1:
        node_bbox = node.get('absoluteBoundingBox', {})
        node_w = node_bbox.get('width', 0)
        # Check 1: parent clips this node and node is wider than parent
        if parent_node and parent_node.get('clipsContent', False):
            parent_bbox = parent_node.get('absoluteBoundingBox', {})
            parent_w = parent_bbox.get('width', 0)
            if parent_w > 0 and node_w > parent_w + 1:
                needs_scroll = True
        # Check 2: this node clips its own content
        if not needs_scroll and node.get('clipsContent', False):
            children_total_w = sum(
                c.get('absoluteBoundingBox', {}).get('width', 0)
                for c in visible_children
                if c.get('absoluteBoundingBox')
            )
            children_total_w += gap * max(0, len(visible_children) - 1)
            if children_total_w > node_w + 1:
                needs_scroll = True
        # Check 3: content significantly wider than node's own frame
        if not needs_scroll and node_w > 0:
            children_total_w = sum(
                c.get('absoluteBoundingBox', {}).get('width', 0)
                for c in visible_children
                if c.get('absoluteBoundingBox')
            )
            children_total_w += gap * max(0, len(visible_children) - 1)
            if children_total_w > node_w * 1.1:
                needs_scroll = True

    if needs_wrap:
        # Use LazyVGrid with adaptive columns for wrapping layout
        # Estimate minimum item width from first child
        first_child_w = 50
        if visible_children:
            fb = visible_children[0].get('absoluteBoundingBox', {})
            first_child_w = max(20, int(fb.get('width', 50)))
        wrap_gap = int(gap) if gap else 8
        lines.append(f'{prefix}let columns = [GridItem(.adaptive(minimum: {first_child_w}), spacing: {wrap_gap})]')
        lines.append(f'{prefix}LazyVGrid(columns: columns, alignment: .leading, spacing: {wrap_gap}) {{')
    elif needs_scroll:
        lines.append(f'{prefix}ScrollView(.horizontal, showsIndicators: false) {{')
        lines.append(f'{prefix}    {container}({params_str}) {{')
    else:
        # Open container
        lines.append(f'{prefix}{container}({params_str}) {{')

    # For ZStack with absolute positioning, calculate offsets from container origin
    container_bbox = node.get('absoluteBoundingBox', {})
    container_x = container_bbox.get('x', 0)
    container_y = container_bbox.get('y', 0)
    container_w = container_bbox.get('width', 0)
    container_h = container_bbox.get('height', 0)
    use_offsets = (container == 'ZStack' and len(visible_children) > 1)

    # Render children recursively
    child_count = 0
    for i, child in enumerate(visible_children):
        if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
            lines.append(f'{prefix}    // ... {len(visible_children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
            break
        child_code = _generate_swiftui_node(child, indent + 4, depth + 1, parent_node=node)
        if child_code:
            # Add offset for ZStack children based on absolute position
            if use_offsets:
                child_bbox = child.get('absoluteBoundingBox', {})
                if child_bbox:
                    child_w = child_bbox.get('width', 0)
                    child_h = child_bbox.get('height', 0)
                    # Calculate offset from container center (ZStack default alignment)
                    offset_x = (child_bbox.get('x', 0) + child_w / 2) - (container_x + container_w / 2)
                    offset_y = (child_bbox.get('y', 0) + child_h / 2) - (container_y + container_h / 2)
                    if abs(offset_x) > 1 or abs(offset_y) > 1:
                        child_code += f'\n{prefix}        .offset(x: {int(offset_x)}, y: {int(offset_y)})'
            lines.append(child_code)
            child_count += 1
            if primary_align == 'SPACE_BETWEEN' and i < len(visible_children) - 1:
                lines.append(f'{prefix}    Spacer()')

    # Close container
    if needs_wrap:
        lines.append(f'{prefix}}}')      # close LazyVGrid
    elif needs_scroll:
        lines.append(f'{prefix}    }}')  # close HStack
        lines.append(f'{prefix}}}')      # close ScrollView
    else:
        lines.append(f'{prefix}}}')

    # Collect and apply modifiers (deduplicate consecutive identical modifiers)
    modifiers, gradient_def = _swiftui_collect_modifiers(node)
    if gradient_def:
        lines.append(gradient_def)
    prev_mod = None
    for mod in modifiers:
        if mod != prev_mod:
            lines.append(f'{prefix}{mod}')
        prev_mod = mod

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

_sanitize_component_name = sanitize_component_name  # Use shared sanitizer from base


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
        # Smart heuristic for root container too
        children = node.get('children', [])
        container_bbox = node.get('absoluteBoundingBox', {})
        container, inferred_gap = _analyze_children_layout(children, container_bbox)
        if container == 'VStack':
            alignment = '.leading'
            gap = inferred_gap
        elif container == 'HStack':
            alignment = '.center'
            gap = inferred_gap
        else:
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
    visible_children = [c for c in children if c.get('visible', True)]

    # ZStack offset calculation for root container
    root_bbox = node.get('absoluteBoundingBox', {})
    root_x = root_bbox.get('x', 0)
    root_y = root_bbox.get('y', 0)
    root_w = root_bbox.get('width', 0)
    root_h = root_bbox.get('height', 0)
    use_root_offsets = (container == 'ZStack' and len(visible_children) > 1)

    children_lines = []
    child_count = 0
    for child in visible_children:
        if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
            children_lines.append(f'            // ... {len(visible_children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
            break
        child_code = _generate_swiftui_node(child, indent=12, depth=1, parent_node=node)
        if child_code:
            # Add offset for ZStack children in root container
            if use_root_offsets:
                child_bbox = child.get('absoluteBoundingBox', {})
                if child_bbox:
                    child_w = child_bbox.get('width', 0)
                    child_h = child_bbox.get('height', 0)
                    offset_x = (child_bbox.get('x', 0) + child_w / 2) - (root_x + root_w / 2)
                    offset_y = (child_bbox.get('y', 0) + child_h / 2) - (root_y + root_h / 2)
                    if abs(offset_x) > 1 or abs(offset_y) > 1:
                        child_code += f'\n                .offset(x: {int(offset_x)}, y: {int(offset_y)})'
            children_lines.append(child_code)
            child_count += 1

    children_code = '\n'.join(children_lines) if children_lines else '            // Content'

    # Detect horizontal overflow for root → wrap in ScrollView(.horizontal)
    root_needs_scroll = False
    if container == 'HStack':
        root_bbox = node.get('absoluteBoundingBox', {})
        root_w = root_bbox.get('width', 0)
        if root_w > 0:
            children_total_w = sum(
                c.get('absoluteBoundingBox', {}).get('width', 0)
                for c in visible_children
                if c.get('absoluteBoundingBox')
            )
            children_total_w += gap * max(0, len(visible_children) - 1)
            if children_total_w > root_w * 1.05:
                root_needs_scroll = True

    # Detect mobile frame pattern for vertical ScrollView
    # Mobile frames: width 375-430, height > 900, or tall aspect ratio
    mobile_needs_vscroll = False
    is_mobile_width = 375 <= root_w <= 430
    is_tall_content = root_h > 900
    aspect_ratio = root_h / root_w if root_w > 0 else 0
    is_tall_aspect = aspect_ratio > 2.5

    # If ZStack was chosen but frame is mobile + tall → use ScrollView + VStack instead
    if container == 'ZStack' and is_mobile_width and (is_tall_content or is_tall_aspect):
        mobile_needs_vscroll = True
        # Override: convert ZStack to VStack for scrollable mobile UI
        container = 'VStack'
        alignment = '.leading'
        params = []
        if alignment != '.center':
            params.append(f"alignment: {alignment}")
        if gap:
            params.append(f"spacing: {int(gap)}")
        params_str = ', '.join(params)
        # Regenerate children without offsets
        children_lines = []
        child_count = 0
        for child in visible_children:
            if child_count >= MAX_NATIVE_CHILDREN_LIMIT:
                children_lines.append(f'            // ... {len(visible_children) - MAX_NATIVE_CHILDREN_LIMIT} more children truncated')
                break
            child_code = _generate_swiftui_node(child, indent=12, depth=1, parent_node=node)
            if child_code:
                children_lines.append(child_code)
                child_count += 1
        children_code = '\n'.join(children_lines) if children_lines else '            // Content'

    if root_needs_scroll:
        body_content = f"""ScrollView(.horizontal, showsIndicators: false) {{
            {container}({params_str}) {{
{children_code}
            }}
        }}"""
    elif mobile_needs_vscroll:
        body_content = f"""ScrollView(showsIndicators: false) {{
            {container}({params_str}) {{
{children_code}
            }}
        }}"""
    else:
        body_content = f"""{container}({params_str}) {{
{children_code}
        }}"""

    code = f'''import SwiftUI

struct {component_name}: View {{{gradient_section}
    var body: some View {{
        {body_content}
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
