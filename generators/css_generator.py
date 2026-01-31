"""
CSS / SCSS Code Generator - Pure CSS, SCSS, CSS variables, and Tailwind config.

Generates CSS and SCSS code from Figma node data including:
fills (solid, gradient, image, layered), strokes, corner radius, shadows,
blur, opacity, blend modes, rotation, padding, auto-layout, text styling,
hyperlinks, line clamping, paragraph spacing, and design-token variables.
"""

from typing import Dict, Any, List, Literal

# Import shared constants from base module
from generators.base import MAX_CHILDREN_LIMIT

# Import helper functions from the main figma_mcp module.
# These will be migrated to generators.base in a future task.
from figma_mcp import (
    _get_background_css,
    _extract_stroke_data,
    _extract_effects_data,
    _corner_radii_to_css,
    _transform_to_css,
    _blend_mode_to_css,
    _text_case_to_css,
    _text_decoration_to_css,
    _sanitize_token_name,
    _extract_gradient_stops,
    _rgba_to_hex,
)


# ---------------------------------------------------------------------------
# Design-token variable generators
# ---------------------------------------------------------------------------

def generate_style_variables(
    colors: List[Dict],
    typography: List[Dict],
    spacing: List[Dict],
    effects: List[Dict],
    format: Literal['css', 'scss'] = 'css',
) -> str:
    """Generate CSS or SCSS variables from design tokens.

    Args:
        colors: List of color tokens
        typography: List of typography tokens
        spacing: List of spacing tokens
        effects: List of effect tokens (shadows, blurs)
        format: Output format - 'css' or 'scss'
    """
    is_css = format == 'css'
    prefix = '--' if is_css else '$'
    indent = '  ' if is_css else ''
    comment = lambda text: f"  /* {text} */" if is_css else f"// {text}"

    lines: List[str] = []

    # Header
    if is_css:
        lines.append(":root {")
        lines.append(comment("Colors"))
    else:
        lines.extend(["// Design Tokens - Generated from Figma", "", "// Colors"])

    # Colors (deduplicated)
    seen_colors: set = set()
    for color in colors:
        hex_val = color.get('hex') or color.get('color', '')
        if hex_val and hex_val not in seen_colors and not hex_val.startswith('/*'):
            seen_colors.add(hex_val)
            name = _sanitize_token_name(color.get('name', 'color'))
            category = color.get('category', 'fill')
            lines.append(f"{indent}{prefix}color-{category}-{name}: {hex_val};")

    # Typography (deduplicated by font family)
    if typography:
        lines.append("")
        lines.append(comment("Typography"))
        seen_fonts: set = set()
        for typo in typography:
            font_family = typo.get('fontFamily', 'sans-serif')
            if font_family not in seen_fonts:
                seen_fonts.add(font_family)
                name = _sanitize_token_name(font_family)
                lines.append(f"{indent}{prefix}font-family-{name}: '{font_family}', sans-serif;")
                lines.append(f"{indent}{prefix}font-size-{name}: {typo.get('fontSize', 16)}px;")
                lines.append(f"{indent}{prefix}font-weight-{name}: {typo.get('fontWeight', 400)};")
                if is_css and typo.get('lineHeight'):
                    lines.append(f"{indent}{prefix}line-height-{name}: {typo.get('lineHeight')}px;")

    # Spacing (deduplicated)
    if spacing:
        lines.append("")
        lines.append(comment("Spacing"))
        seen_spacing: set = set()
        for sp in spacing:
            if sp.get('type') == 'auto-layout':
                name = _sanitize_token_name(sp.get('name', 'spacing'))
                padding = sp.get('padding', {})
                gap = sp.get('gap', 0)
                key = f"{padding.get('top', 0)}-{padding.get('right', 0)}-{gap}"
                if key not in seen_spacing:
                    seen_spacing.add(key)
                    if is_css:
                        lines.append(f"{indent}{prefix}spacing-{name}-padding: {padding.get('top', 0)}px {padding.get('right', 0)}px {padding.get('bottom', 0)}px {padding.get('left', 0)}px;")
                    lines.append(f"{indent}{prefix}spacing-{name}-gap: {gap}px;")

    # Shadows (deduplicated)
    if effects:
        lines.append("")
        lines.append(comment("Shadows"))
        seen_shadows: set = set()
        for effect in effects:
            if effect.get('type') in ['DROP_SHADOW', 'INNER_SHADOW']:
                hex_val = effect.get('hex') or effect.get('color', '#000')
                offset = effect.get('offset', {})
                x = offset.get('x', 0)
                y = offset.get('y', 0)
                blur = effect.get('radius', 0)
                spread = effect.get('spread', 0)
                key = f"{hex_val}-{x}-{y}-{blur}"
                if key not in seen_shadows:
                    seen_shadows.add(key)
                    name = _sanitize_token_name(effect.get('name', 'shadow'))
                    inset = 'inset ' if effect.get('type') == 'INNER_SHADOW' else ''
                    lines.append(f"{indent}{prefix}shadow-{name}: {inset}{x}px {y}px {blur}px {spread}px {hex_val};")

    # Footer
    if is_css:
        lines.append("}")

    return "\n".join(lines)


def generate_css_variables(
    colors: List[Dict],
    typography: List[Dict],
    spacing: List[Dict],
    effects: List[Dict],
) -> str:
    """Generate CSS custom properties from design tokens."""
    return generate_style_variables(colors, typography, spacing, effects, format='css')


def generate_scss_variables(
    colors: List[Dict],
    typography: List[Dict],
    spacing: List[Dict],
    effects: List[Dict],
) -> str:
    """Generate SCSS variables from design tokens."""
    return generate_style_variables(colors, typography, spacing, effects, format='scss')


def generate_tailwind_config(
    colors: List[Dict],
    typography: List[Dict],
    spacing: List[Dict],
) -> str:
    """Generate Tailwind CSS theme extension from design tokens."""
    # Collect unique colors
    color_entries: Dict[str, str] = {}
    for color in colors:
        hex_val = color.get('hex') or color.get('color', '')
        if hex_val and not hex_val.startswith('/*') and not hex_val.startswith('rgba'):
            name = _sanitize_token_name(color.get('name', 'color'))
            if name not in color_entries:
                color_entries[name] = hex_val

    # Collect font families
    font_entries: Dict[str, str] = {}
    for typo in typography:
        font_family = typo.get('fontFamily', '')
        if font_family:
            name = _sanitize_token_name(font_family)
            if name not in font_entries:
                font_entries[name] = f"['{font_family}', 'sans-serif']"

    # Collect spacing values
    spacing_entries: Dict[str, str] = {}
    for sp in spacing:
        if sp.get('type') == 'auto-layout':
            gap = sp.get('gap', 0)
            if gap > 0:
                spacing_entries[str(gap)] = f"'{gap}px'"

    # Build config
    lines = [
        "// tailwind.config.js - Generated from Figma",
        "module.exports = {",
        "  theme: {",
        "    extend: {"
    ]

    # Colors
    if color_entries:
        lines.append("      colors: {")
        for name, hex_val in color_entries.items():
            lines.append(f"        '{name}': '{hex_val}',")
        lines.append("      },")

    # Fonts
    if font_entries:
        lines.append("      fontFamily: {")
        for name, value in font_entries.items():
            lines.append(f"        '{name}': {value},")
        lines.append("      },")

    # Spacing
    if spacing_entries:
        lines.append("      spacing: {")
        for key, value in spacing_entries.items():
            lines.append(f"        '{key}': {value},")
        lines.append("      },")

    lines.extend([
        "    }",
        "  }",
        "}"
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSS code generator
# ---------------------------------------------------------------------------

def generate_css_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate pure CSS code from Figma node with enhanced style support."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 'auto')
    height = bbox.get('height', 'auto')

    # Background (with gradient, image, and layered support)
    bg_value, bg_type = _get_background_css(node)
    bg_css = ''
    if bg_value and bg_type:
        if bg_type == 'color':
            bg_css = f"background-color: {bg_value};"
        elif bg_type in ('gradient', 'image', 'layered'):
            # Use 'background' shorthand for gradients, images, and layered backgrounds
            bg_css = f"background: {bg_value};"

    # Strokes (comprehensive)
    stroke_data = _extract_stroke_data(node)
    stroke_css = ''
    if stroke_data and stroke_data['colors']:
        first_stroke = stroke_data['colors'][0]
        if first_stroke.get('type') == 'SOLID':
            stroke_color = first_stroke.get('color', '')
            stroke_weight = stroke_data['weight']
            stroke_css = f"border: {stroke_weight}px solid {stroke_color};"

    # Border radius (with individual corners)
    corner_radius_css = _corner_radii_to_css(node)
    radius_css = f"border-radius: {corner_radius_css};" if corner_radius_css else ''

    # Transform (rotation, scale)
    transform_css = _transform_to_css(node)
    transform_line = f"transform: {transform_css};" if transform_css else ''

    # Blend mode
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_mode_css = _blend_mode_to_css(blend_mode)
    blend_line = f"mix-blend-mode: {blend_mode_css};" if blend_mode_css else ''

    # Opacity
    opacity = node.get('opacity', 1)
    opacity_css = f"opacity: {opacity};" if opacity < 1 else ''

    # Auto-layout
    layout_mode = node.get('layoutMode')
    layout_css = ''
    if layout_mode:
        direction = 'column' if layout_mode == 'VERTICAL' else 'row'
        gap = node.get('itemSpacing', 0)
        padding_top = node.get('paddingTop', 0)
        padding_right = node.get('paddingRight', 0)
        padding_bottom = node.get('paddingBottom', 0)
        padding_left = node.get('paddingLeft', 0)

        # Alignment
        primary_align = node.get('primaryAxisAlignItems', 'MIN')
        counter_align = node.get('counterAxisAlignItems', 'MIN')
        justify_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}
        items_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end'}

        layout_css = f"""display: flex;
  flex-direction: {direction};
  gap: {gap}px;
  padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;
  justify-content: {justify_map.get(primary_align, 'flex-start')};
  align-items: {items_map.get(counter_align, 'flex-start')};"""

    # Flex child properties (layoutGrow, layoutPositioning, layoutAlign)
    flex_child_css = ''
    layout_grow = node.get('layoutGrow', 0)
    layout_positioning = node.get('layoutPositioning')
    layout_align = node.get('layoutAlign')

    flex_child_lines = []
    if layout_grow and layout_grow > 0:
        flex_child_lines.append(f"flex-grow: {layout_grow};")
    if layout_positioning == 'ABSOLUTE':
        flex_child_lines.append("position: absolute;")
    if layout_align == 'STRETCH':
        flex_child_lines.append("align-self: stretch;")
    elif layout_align == 'INHERIT':
        flex_child_lines.append("align-self: auto;")

    if flex_child_lines:
        flex_child_css = '\n  '.join(flex_child_lines)

    # Effects (shadows and blurs)
    effects_data = _extract_effects_data(node)
    shadow_css = ''
    blur_css = ''

    if effects_data['shadows']:
        shadow_parts = []
        for shadow in effects_data['shadows']:
            offset = shadow.get('offset', {'x': 0, 'y': 0})
            shadow_type = shadow.get('type', 'DROP_SHADOW')
            inset = 'inset ' if shadow_type == 'INNER_SHADOW' else ''
            shadow_parts.append(
                f"{inset}{int(offset.get('x', 0))}px {int(offset.get('y', 0))}px {int(shadow.get('radius', 0))}px {int(shadow.get('spread', 0))}px {shadow.get('color', '#000')}"
            )
        shadow_css = f"box-shadow: {', '.join(shadow_parts)};"

    if effects_data['blurs']:
        for blur in effects_data['blurs']:
            if blur.get('type') == 'LAYER_BLUR':
                blur_css = f"filter: blur({int(blur.get('radius', 0))}px);"
            elif blur.get('type') == 'BACKGROUND_BLUR':
                blur_css = f"backdrop-filter: blur({int(blur.get('radius', 0))}px);"

    # Text-specific styles (for TEXT nodes)
    text_css = ''
    text_decoration_css = ''
    hyperlink_comment = ''
    if node.get('type') == 'TEXT':
        style = node.get('style', {})

        # Get hyperlink if present (CSS can't create links, but we add a comment)
        hyperlink = node.get('hyperlink')
        if hyperlink and hyperlink.get('type') == 'URL':
            hyperlink_comment = f"/* Hyperlink: {hyperlink.get('url', '')} - Use <a> tag in HTML */"

        # Text transform (textCase)
        text_case = style.get('textCase', 'ORIGINAL')
        text_transform = _text_case_to_css(text_case)
        if text_transform:
            text_css = f"text-transform: {text_transform};"

        # Text decoration
        text_decoration = style.get('textDecoration', 'NONE')
        text_dec_value = _text_decoration_to_css(text_decoration)
        if text_dec_value:
            text_decoration_css = f"text-decoration: {text_dec_value};"

        # Font properties
        font_family = style.get('fontFamily', 'sans-serif')
        font_size = style.get('fontSize', 16)
        font_weight = style.get('fontWeight', 400)
        line_height = style.get('lineHeightPx')
        letter_spacing = style.get('letterSpacing', 0)
        text_align = style.get('textAlignHorizontal', 'LEFT').lower()

        text_css_lines = []
        if hyperlink_comment:
            text_css_lines.append(hyperlink_comment)
        text_css_lines.extend([
            f"font-family: '{font_family}', sans-serif;",
            f"font-size: {font_size}px;",
            f"font-weight: {font_weight};",
        ])
        if line_height:
            text_css_lines.append(f"line-height: {line_height}px;")
        if letter_spacing:
            text_css_lines.append(f"letter-spacing: {letter_spacing}px;")
        if text_align != 'left':
            text_css_lines.append(f"text-align: {text_align};")
        if text_transform:
            text_css_lines.append(f"text-transform: {text_transform};")
        if text_dec_value:
            text_css_lines.append(f"text-decoration: {text_dec_value};")

        # Text truncation (maxLines + textTruncation)
        max_lines = style.get('maxLines')
        text_truncation = style.get('textTruncation', 'DISABLED')
        if max_lines and max_lines > 0:
            text_css_lines.append("display: -webkit-box;")
            text_css_lines.append(f"-webkit-line-clamp: {max_lines};")
            text_css_lines.append("-webkit-box-orient: vertical;")
            text_css_lines.append("overflow: hidden;")
            if text_truncation == 'ENDING':
                text_css_lines.append("text-overflow: ellipsis;")

        # Paragraph spacing and indent
        paragraph_spacing = style.get('paragraphSpacing', 0)
        paragraph_indent = style.get('paragraphIndent', 0)
        if paragraph_spacing and paragraph_spacing > 0:
            text_css_lines.append(f"margin-bottom: {paragraph_spacing}px; /* paragraph spacing */")
        if paragraph_indent and paragraph_indent > 0:
            text_css_lines.append(f"text-indent: {paragraph_indent}px;")

        text_css = '\n  '.join(text_css_lines)

    # Build final CSS
    css_lines = [
        f"width: {int(width)}px;",
        f"height: {int(height)}px;",
    ]

    if bg_css:
        css_lines.append(bg_css)
    if stroke_css:
        css_lines.append(stroke_css)
    if radius_css:
        css_lines.append(radius_css)
    if transform_line:
        css_lines.append(transform_line)
    if blend_line:
        css_lines.append(blend_line)
    if opacity_css:
        css_lines.append(opacity_css)
    if shadow_css:
        css_lines.append(shadow_css)
    if blur_css:
        css_lines.append(blur_css)
    if layout_css:
        css_lines.append(layout_css)
    if flex_child_css:
        css_lines.append(flex_child_css)
    if text_css:
        css_lines.append(text_css)

    css_content = '\n  '.join(css_lines)

    code = f'''.{component_name.lower()} {{
  {css_content}
}}'''
    return code


# ---------------------------------------------------------------------------
# SCSS code generator
# ---------------------------------------------------------------------------

def generate_scss_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate SCSS code with variables from Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 'auto')
    height = bbox.get('height', 'auto')

    # Background (with gradient support)
    bg_value, bg_type = _get_background_css(node)

    # Individual corner radii
    border_radius_css = _corner_radii_to_css(node)

    # Transform (rotation, scale)
    transform_css = _transform_to_css(node)

    # Blend mode
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_mode_css = _blend_mode_to_css(blend_mode)

    # Opacity
    opacity = node.get('opacity', 1)

    # Effects (shadows and blurs)
    effects = node.get('effects', [])
    shadow_parts = []
    blur_value = None
    backdrop_blur = None

    for effect in effects:
        if not effect.get('visible', True):
            continue
        effect_type = effect.get('type', '')
        if effect_type in ['DROP_SHADOW', 'INNER_SHADOW']:
            color = effect.get('color', {})
            offset_x = effect.get('offset', {}).get('x', 0)
            offset_y = effect.get('offset', {}).get('y', 0)
            blur = effect.get('radius', 0)
            spread = effect.get('spread', 0)
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            a = color.get('a', 1)
            inset = 'inset ' if effect_type == 'INNER_SHADOW' else ''
            shadow_parts.append(f'{inset}{offset_x}px {offset_y}px {blur}px {spread}px rgba({r}, {g}, {b}, {a:.2f})')
        elif effect_type == 'LAYER_BLUR':
            blur_value = effect.get('radius', 0)
        elif effect_type == 'BACKGROUND_BLUR':
            backdrop_blur = effect.get('radius', 0)

    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Advanced layout properties
    primary_align = node.get('primaryAxisAlignItems', 'MIN')
    counter_align = node.get('counterAxisAlignItems', 'MIN')
    layout_wrap = node.get('layoutWrap', 'NO_WRAP')

    # Map Figma alignment to CSS
    align_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}
    justify_content = align_map.get(primary_align, 'flex-start')
    align_items = align_map.get(counter_align, 'flex-start')

    # Build SCSS variables
    variables_list = [
        f'// {component_name} Variables',
        f'$width: {int(width)}px;',
        f'$height: {int(height)}px;',
    ]

    if bg_type == 'color' and bg_value:
        variables_list.append(f'$bg-color: {bg_value};')
    elif bg_type == 'gradient' and bg_value:
        variables_list.append(f'$bg-gradient: {bg_value};')

    variables_list.append(f'$border-radius: {border_radius_css};')
    variables_list.append(f'$gap: {gap}px;')
    variables_list.append(f'$padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;')

    if shadow_parts:
        variables_list.append(f'$box-shadow: {", ".join(shadow_parts)};')
    if opacity < 1:
        variables_list.append(f'$opacity: {opacity:.2f};')
    if transform_css:
        variables_list.append(f'$transform: {transform_css};')

    variables = '\n'.join(variables_list)

    # Build styles
    styles_list = [
        'width: $width;',
        'height: $height;',
    ]

    if bg_type == 'color':
        styles_list.append('background-color: $bg-color;')
    elif bg_type == 'gradient':
        styles_list.append('background: $bg-gradient;')
    elif bg_type == 'image':
        styles_list.append(f'background: url("{bg_value}") center/cover no-repeat;')
    elif bg_type == 'layered':
        # Layered backgrounds (multiple fills combined)
        styles_list.append(f'background: {bg_value};')

    styles_list.append('border-radius: $border-radius;')

    if shadow_parts:
        styles_list.append('box-shadow: $box-shadow;')

    if opacity < 1:
        styles_list.append('opacity: $opacity;')

    if transform_css:
        styles_list.append('transform: $transform;')

    if blend_mode_css:
        styles_list.append(f'mix-blend-mode: {blend_mode_css};')

    if blur_value:
        styles_list.append(f'filter: blur({blur_value}px);')

    if backdrop_blur:
        styles_list.append(f'backdrop-filter: blur({backdrop_blur}px);')

    if layout_mode:
        styles_list.extend([
            'display: flex;',
            f'flex-direction: {"column" if layout_mode == "VERTICAL" else "row"};',
            f'justify-content: {justify_content};',
            f'align-items: {align_items};',
            'gap: $gap;',
            'padding: $padding;',
        ])
        if layout_wrap == 'WRAP':
            styles_list.append('flex-wrap: wrap;')

    # Flex child properties (layoutGrow, layoutPositioning, layoutAlign)
    layout_grow = node.get('layoutGrow', 0)
    layout_positioning = node.get('layoutPositioning')
    layout_align = node.get('layoutAlign')

    if layout_grow and layout_grow > 0:
        styles_list.append(f'flex-grow: {layout_grow};')
    if layout_positioning == 'ABSOLUTE':
        styles_list.append('position: absolute;')
    if layout_align == 'STRETCH':
        styles_list.append('align-self: stretch;')
    elif layout_align == 'INHERIT':
        styles_list.append('align-self: auto;')

    # Text-specific styles (for TEXT nodes)
    if node.get('type') == 'TEXT':
        style = node.get('style', {})
        font_family = style.get('fontFamily', 'sans-serif')
        font_size = style.get('fontSize', 16)
        font_weight = style.get('fontWeight', 400)
        line_height = style.get('lineHeightPx')
        letter_spacing = style.get('letterSpacing', 0)
        text_align = style.get('textAlignHorizontal', 'LEFT').lower()
        text_case = style.get('textCase', 'ORIGINAL')
        text_decoration = style.get('textDecoration', 'NONE')

        # Get hyperlink if present (SCSS can't create links, but we add a comment)
        hyperlink = node.get('hyperlink')
        if hyperlink and hyperlink.get('type') == 'URL':
            styles_list.insert(0, f"// Hyperlink: {hyperlink.get('url', '')} - Use <a> tag in HTML")

        # Add typography variables
        variables_list.insert(-1, f"$font-family: '{font_family}', sans-serif;")
        variables_list.insert(-1, f'$font-size: {font_size}px;')
        variables_list.insert(-1, f'$font-weight: {font_weight};')

        styles_list.extend([
            'font-family: $font-family;',
            'font-size: $font-size;',
            'font-weight: $font-weight;',
        ])
        if line_height:
            styles_list.append(f'line-height: {line_height}px;')
        if letter_spacing:
            styles_list.append(f'letter-spacing: {letter_spacing}px;')
        if text_align != 'left':
            styles_list.append(f'text-align: {text_align};')

        text_transform = _text_case_to_css(text_case)
        if text_transform:
            styles_list.append(f'text-transform: {text_transform};')

        text_dec_value = _text_decoration_to_css(text_decoration)
        if text_dec_value:
            styles_list.append(f'text-decoration: {text_dec_value};')

        # Text truncation (maxLines + textTruncation)
        max_lines = style.get('maxLines')
        text_truncation = style.get('textTruncation', 'DISABLED')
        if max_lines and max_lines > 0:
            styles_list.append('display: -webkit-box;')
            styles_list.append(f'-webkit-line-clamp: {max_lines};')
            styles_list.append('-webkit-box-orient: vertical;')
            styles_list.append('overflow: hidden;')
            if text_truncation == 'ENDING':
                styles_list.append('text-overflow: ellipsis;')

        # Paragraph spacing and indent
        paragraph_spacing = style.get('paragraphSpacing', 0)
        paragraph_indent = style.get('paragraphIndent', 0)
        if paragraph_spacing and paragraph_spacing > 0:
            styles_list.append(f'margin-bottom: {paragraph_spacing}px; // paragraph spacing')
        if paragraph_indent and paragraph_indent > 0:
            styles_list.append(f'text-indent: {paragraph_indent}px;')

    styles = '\n  '.join(styles_list)

    code = f'''{variables}

.{component_name.lower().replace(" ", "-")} {{
  {styles}
}}'''
    return code


# ---------------------------------------------------------------------------
# Backward-compatible aliases (match the private names in figma_mcp.py)
# ---------------------------------------------------------------------------

_generate_css_code = generate_css_code
_generate_scss_code = generate_scss_code
_generate_css_variables = generate_css_variables
_generate_scss_variables = generate_scss_variables
_generate_tailwind_config = generate_tailwind_config
_generate_style_variables = generate_style_variables
