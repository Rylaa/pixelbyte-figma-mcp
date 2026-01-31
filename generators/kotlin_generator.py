"""
Kotlin Code Generator - Jetpack Compose rendering with full property support.

Generates Kotlin Jetpack Compose code from Figma node trees.
Supports: fills (solid, linear gradient, radial gradient), corner radius,
shadows, blur, opacity, blend modes, rotation, padding, auto-layout,
text styling, hyperlinks, line clamping, and paragraph spacing.
"""

from typing import Dict, Any, List

# Import shared constants from base module
from generators.base import (
    KOTLIN_WEIGHT_MAP,
    MAX_NATIVE_CHILDREN_LIMIT,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_kotlin_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate Kotlin Jetpack Compose code from Figma node with comprehensive style support."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 100)
    height = bbox.get('height', 100)

    # Background (with gradient support)
    fills = node.get('fills', [])
    bg_code = ''
    gradient_import = ''
    brush_def = ''

    for fill in fills:
        if not fill.get('visible', True):
            continue
        fill_type = fill.get('type', '')

        if fill_type == 'SOLID':
            color = fill.get('color', {})
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            a = fill.get('opacity', color.get('a', 1))
            bg_code = f".background(Color(0x{int(a*255):02X}{r:02X}{g:02X}{b:02X}))"
            break

        elif fill_type == 'GRADIENT_LINEAR':
            stops = fill.get('gradientStops', [])
            if stops:
                gradient_import = 'import androidx.compose.ui.graphics.Brush'
                colors = []
                for stop in stops:
                    c = stop.get('color', {})
                    sr = int(c.get('r', 0) * 255)
                    sg = int(c.get('g', 0) * 255)
                    sb = int(c.get('b', 0) * 255)
                    colors.append(f"Color(0xFF{sr:02X}{sg:02X}{sb:02X})")
                brush_def = f'''    val gradientBrush = Brush.horizontalGradient(
        colors = listOf({", ".join(colors)})
    )
'''
                bg_code = '.background(gradientBrush)'
            break

        elif fill_type == 'GRADIENT_RADIAL':
            stops = fill.get('gradientStops', [])
            if stops:
                gradient_import = 'import androidx.compose.ui.graphics.Brush'
                colors = []
                for stop in stops:
                    c = stop.get('color', {})
                    sr = int(c.get('r', 0) * 255)
                    sg = int(c.get('g', 0) * 255)
                    sb = int(c.get('b', 0) * 255)
                    colors.append(f"Color(0xFF{sr:02X}{sg:02X}{sb:02X})")
                brush_def = f'''    val gradientBrush = Brush.radialGradient(
        colors = listOf({", ".join(colors)})
    )
'''
                bg_code = '.background(gradientBrush)'
            break

    # Individual corner radii
    corner_radii = node.get('rectangleCornerRadii', [])
    corner_radius = node.get('cornerRadius', 0)
    corner_code = ''

    if corner_radii and len(corner_radii) == 4:
        tl, tr, br, bl = corner_radii
        if tl == tr == br == bl:
            corner_code = f'.clip(RoundedCornerShape({tl}.dp))' if tl > 0 else ''
        else:
            corner_code = f'.clip(RoundedCornerShape(topStart = {tl}.dp, topEnd = {tr}.dp, bottomEnd = {br}.dp, bottomStart = {bl}.dp))'
    elif corner_radius:
        corner_code = f'.clip(RoundedCornerShape({corner_radius}.dp))'

    # Rotation
    rotation = node.get('rotation', 0)
    rotation_code = f'.rotate({rotation:.1f}f)' if rotation != 0 else ''
    rotation_import = 'import androidx.compose.ui.draw.rotate' if rotation != 0 else ''

    # Opacity (alpha)
    opacity = node.get('opacity', 1)
    alpha_code = f'.alpha({opacity:.2f}f)' if opacity < 1 else ''
    alpha_import = 'import androidx.compose.ui.draw.alpha' if opacity < 1 else ''

    # Blend mode
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_map = {
        'MULTIPLY': 'BlendMode.Multiply', 'SCREEN': 'BlendMode.Screen',
        'OVERLAY': 'BlendMode.Overlay', 'DARKEN': 'BlendMode.Darken',
        'LIGHTEN': 'BlendMode.Lighten', 'COLOR_DODGE': 'BlendMode.ColorDodge',
        'COLOR_BURN': 'BlendMode.ColorBurn', 'SOFT_LIGHT': 'BlendMode.Softlight',
        'HARD_LIGHT': 'BlendMode.Hardlight', 'DIFFERENCE': 'BlendMode.Difference',
        'EXCLUSION': 'BlendMode.Exclusion'
    }
    blend_import = 'import androidx.compose.ui.graphics.BlendMode' if blend_mode in blend_map else ''

    # Effects (shadows and blurs)
    effects = node.get('effects', [])
    shadow_code = ''
    blur_code = ''
    shadow_import = ''
    blur_import = ''

    for effect in effects:
        if not effect.get('visible', True):
            continue
        effect_type = effect.get('type', '')

        if effect_type == 'DROP_SHADOW' and not shadow_code:
            color = effect.get('color', {})
            offset_x = effect.get('offset', {}).get('x', 0)
            offset_y = effect.get('offset', {}).get('y', 0)
            blur = effect.get('radius', 0)
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            a = color.get('a', 0.25)
            shadow_import = 'import androidx.compose.ui.draw.shadow'
            shadow_code = f'.shadow(elevation = {blur}.dp, shape = RoundedCornerShape({corner_radius}.dp))'
        elif effect_type == 'LAYER_BLUR' and not blur_code:
            blur_import = 'import androidx.compose.ui.draw.blur'
            blur_code = f'.blur(radius = {effect.get("radius", 0)}.dp)'

    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Advanced alignment
    primary_align = node.get('primaryAxisAlignItems', 'MIN')
    counter_align = node.get('counterAxisAlignItems', 'MIN')

    align_map = {'MIN': 'Start', 'CENTER': 'CenterHorizontally', 'MAX': 'End'}
    v_align_map = {'MIN': 'Top', 'CENTER': 'CenterVertically', 'MAX': 'Bottom'}

    # Determine container type
    container = 'Column' if layout_mode == 'VERTICAL' else 'Row' if layout_mode == 'HORIZONTAL' else 'Box'

    # Generate children
    children_code = generate_kotlin_children(node.get('children', []))

    # Build arrangement
    arrangement_parts = []
    if layout_mode == 'VERTICAL':
        if gap:
            arrangement_parts.append(f'verticalArrangement = Arrangement.spacedBy({gap}.dp)')
        h_align = align_map.get(counter_align, 'Start')
        arrangement_parts.append(f'horizontalAlignment = Alignment.{h_align}')
    elif layout_mode == 'HORIZONTAL':
        if gap:
            arrangement_parts.append(f'horizontalArrangement = Arrangement.spacedBy({gap}.dp)')
        v_align = v_align_map.get(counter_align, 'Top')
        arrangement_parts.append(f'verticalAlignment = Alignment.{v_align}')

    arrangement = ',\n        '.join(arrangement_parts) if arrangement_parts else ''

    # Build modifier chain
    modifiers = [f'.width({int(width)}.dp)', f'.height({int(height)}.dp)']
    if shadow_code:
        modifiers.append(shadow_code)
    if bg_code:
        modifiers.append(bg_code)
    if corner_code:
        modifiers.append(corner_code)
    if blur_code:
        modifiers.append(blur_code)
    if rotation_code:
        modifiers.append(rotation_code)
    if alpha_code:
        modifiers.append(alpha_code)
    modifiers.append(f'''.padding(
                top = {padding_top}.dp,
                end = {padding_right}.dp,
                bottom = {padding_bottom}.dp,
                start = {padding_left}.dp
            )''')

    modifiers_str = '\n            '.join(modifiers)

    # Collect imports
    extra_imports = [i for i in [gradient_import, rotation_import, alpha_import, shadow_import, blur_import, blend_import] if i]
    extra_imports_str = '\n'.join(extra_imports)
    if extra_imports_str:
        extra_imports_str = '\n' + extra_imports_str

    code = f'''package com.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp{extra_imports_str}

@Composable
fun {component_name}(
    modifier: Modifier = Modifier
) {{
{brush_def}    {container}(
        modifier = modifier
            {modifiers_str}{f""",
        {arrangement}""" if arrangement else ''}
    ) {{
{children_code if children_code else '        // Content'}
    }}
}}

@Preview
@Composable
fun {component_name}Preview() {{
    {component_name}()
}}
'''
    return code


def generate_kotlin_children(children: List[Dict[str, Any]], indent: int = 8) -> str:
    """Generate Kotlin Compose code for children nodes."""
    lines = []
    prefix = ' ' * indent

    for child in children[:MAX_NATIVE_CHILDREN_LIMIT]:
        node_type = child.get('type', '')
        name = child.get('name', 'Unknown')

        if node_type == 'TEXT':
            text = child.get('characters', name)
            style = child.get('style', {})
            font_size = style.get('fontSize', 16)
            font_weight = style.get('fontWeight', 400)
            text_case = style.get('textCase', 'ORIGINAL')
            text_decoration = style.get('textDecoration', 'NONE')

            # Get hyperlink if present
            hyperlink = child.get('hyperlink')
            hyperlink_url = None
            if hyperlink and hyperlink.get('type') == 'URL':
                hyperlink_url = hyperlink.get('url', '')

            # Build Kotlin weight
            kotlin_weight = KOTLIN_WEIGHT_MAP.get(font_weight, 'FontWeight.Normal')

            # Build text decoration
            text_dec_kotlin = 'TextDecoration.None'
            if text_decoration == 'UNDERLINE':
                text_dec_kotlin = 'TextDecoration.Underline'
            elif text_decoration == 'STRIKETHROUGH':
                text_dec_kotlin = 'TextDecoration.LineThrough'

            # Apply text case transformation
            text_expr = f'"{text}"'
            if text_case == 'UPPER':
                text_expr = f'"{text}".uppercase()'
            elif text_case == 'LOWER':
                text_expr = f'"{text}".lowercase()'
            elif text_case == 'TITLE':
                text_expr = f'"{text}".split(" ").joinToString(" ") {{ it.replaceFirstChar {{ c -> c.titlecase() }} }}'

            # Line limits (maxLines + textTruncation)
            max_lines = style.get('maxLines')
            text_truncation = style.get('textTruncation', 'DISABLED')
            overflow_mode = 'TextOverflow.Ellipsis' if text_truncation == 'ENDING' else 'TextOverflow.Clip'

            # Use ClickableText with hyperlink if present
            if hyperlink_url:
                lines.append(f'{prefix}// Clickable link: {hyperlink_url}')
                lines.append(f'{prefix}ClickableText(')
                lines.append(f'{prefix}    text = AnnotatedString({text_expr}),')
                lines.append(f'{prefix}    style = TextStyle(')
                lines.append(f'{prefix}        fontSize = {int(font_size)}.sp,')
                lines.append(f'{prefix}        fontWeight = {kotlin_weight},')
                lines.append(f'{prefix}        textDecoration = {text_dec_kotlin}')
                lines.append(f'{prefix}    ),')
                if max_lines and max_lines > 0:
                    lines.append(f'{prefix}    maxLines = {max_lines},')
                    lines.append(f'{prefix}    overflow = {overflow_mode},')
                lines.append(f'{prefix}    onClick = {{ uriHandler.openUri("{hyperlink_url}") }}')
                lines.append(f'{prefix})')
            else:
                # Get paragraph spacing for modifier
                paragraph_spacing = style.get('paragraphSpacing', 0)

                lines.append(f'{prefix}Text(')
                lines.append(f'{prefix}    text = {text_expr},')
                if paragraph_spacing and paragraph_spacing > 0:
                    lines.append(f'{prefix}    modifier = Modifier.padding(bottom = {int(paragraph_spacing)}.dp),')
                lines.append(f'{prefix}    fontSize = {int(font_size)}.sp,')
                lines.append(f'{prefix}    fontWeight = {kotlin_weight},')
                if max_lines and max_lines > 0:
                    lines.append(f'{prefix}    maxLines = {max_lines},')
                    lines.append(f'{prefix}    overflow = {overflow_mode},')
                lines.append(f'{prefix}    textDecoration = {text_dec_kotlin}')
                lines.append(f'{prefix})')
        elif node_type in ['FRAME', 'GROUP', 'COMPONENT', 'INSTANCE', 'RECTANGLE']:
            bbox = child.get('absoluteBoundingBox', {})
            w = bbox.get('width', 50)
            h = bbox.get('height', 50)

            fills = child.get('fills', [])
            bg = ''
            if fills and fills[0].get('type') == 'SOLID':
                color = fills[0].get('color', {})
                r = int(color.get('r', 0) * 255)
                g = int(color.get('g', 0) * 255)
                b = int(color.get('b', 0) * 255)
                bg = f".background(Color(0xFF{r:02X}{g:02X}{b:02X}))"

            lines.append(f'{prefix}// {name}')
            lines.append(f'{prefix}Box(')
            lines.append(f'{prefix}    modifier = Modifier')
            lines.append(f'{prefix}        .width({int(w)}.dp)')
            lines.append(f'{prefix}        .height({int(h)}.dp)')
            if bg:
                lines.append(f'{prefix}        {bg}')
            lines.append(f'{prefix})')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Backward-compatible aliases (match the private names used in figma_mcp.py)
# ---------------------------------------------------------------------------

_generate_kotlin_code = generate_kotlin_code
_generate_kotlin_children = generate_kotlin_children
