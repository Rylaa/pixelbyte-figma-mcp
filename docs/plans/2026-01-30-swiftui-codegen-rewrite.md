# SwiftUI & Kotlin Code Generation Rewrite + Truncation Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** SwiftUI ve Kotlin code generation'ı recursive rendering + full property support ile yeniden yazmak, ve design tokens truncation sorununu çözmek.

**Architecture:** SwiftUI ve Kotlin code generation fonksiyonları `figma_mcp.py`'den (6610 satır) ayrı modüllere taşınacak: `swiftui_generator.py` ve `kotlin_generator.py`. React'taki `_recursive_node_to_jsx` modeli referans alınacak - her child node için tüm Figma özellikleri (fill, stroke, corner radius, shadow, opacity, padding, layout) recursive olarak uygulanacak. Truncation için pagination desteği eklenecek.

**Tech Stack:** Python, mevcut figma_mcp.py helper fonksiyonları, Figma REST API

---

### Task 1: `swiftui_generator.py` dosyası oluştur ve helper import'larını ayarla

SwiftUI code generation'ı ayrı bir modüle taşımak için yeni dosyayı oluştur.

**Files:**
- Create: `swiftui_generator.py`

**Step 1: Dosyayı oluştur**

Yeni modül dosyasını oluştur. Gerekli import'ları ve helper referanslarını ekle. Helper fonksiyonlar `figma_mcp.py`'de kalacak - buradan import edilecek.

```python
"""
SwiftUI Code Generator - Recursive rendering with full property support.

Generates production-quality SwiftUI code from Figma node trees.
Supports: fills (solid, gradient, image), strokes, corner radius, shadows,
blur, opacity, blend modes, rotation, padding, auto-layout, text styling.
"""

from typing import Dict, Any, List, Optional

# Import helpers from main module
from figma_mcp import (
    _rgba_to_hex,
    _hex_to_rgb,
    _extract_stroke_data,
    _extract_effects_data,
    _extract_corner_radii,
    _extract_auto_layout,
    SWIFTUI_WEIGHT_MAP,
    MAX_NATIVE_CHILDREN_LIMIT,
)


# Max recursion depth to prevent infinite nesting
MAX_DEPTH = 8
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: create swiftui_generator.py module with helper imports"
```

---

### Task 2: `_generate_swiftui_node` recursive fonksiyonu - temel yapı

Her node tipini (TEXT, FRAME, RECTANGLE, ELLIPSE, VECTOR, COMPONENT, INSTANCE, GROUP) recursive olarak SwiftUI view'a dönüştüren ana fonksiyon.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Recursive node renderer yaz**

```python
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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add recursive _generate_swiftui_node dispatcher"
```

---

### Task 3: `_swiftui_modifiers` - Tüm stil özelliklerini SwiftUI modifier'lara dönüştür

Fills, strokes, corner radius, shadows, blur, opacity, blend mode, rotation, padding - hepsini modifier chain olarak üret.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Modifier builder yaz**

```python
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
    stroke_data = _extract_stroke_data(node)
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
    rgb = _hex_to_rgb(hex_color)
    opacity = first.get('opacity', 1)

    color_code = f"Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f})"
    if opacity < 1:
        color_code += f".opacity({opacity:.2f})"

    return f".overlay(RoundedRectangle(cornerRadius: 0).stroke({color_code}, lineWidth: {weight}))"


def _swiftui_corner_modifier(node: Dict[str, Any]) -> str:
    """Generate SwiftUI corner radius modifier."""
    radii = _extract_corner_radii(node)
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
    effects_data = _extract_effects_data(node)
    modifiers = []

    shadows = effects_data.get('shadows') or []
    blurs = effects_data.get('blurs') or []

    for shadow in shadows:
        if shadow.get('type') == 'DROP_SHADOW':
            color = shadow.get('hex', '#000000')
            rgb = _hex_to_rgb(color)
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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add comprehensive SwiftUI modifier builders (fill, stroke, corner, shadow, opacity)"
```

---

### Task 4: `_swiftui_text_node` - Text rendering

TEXT node'ları için tam SwiftUI rendering: renk, font, line height, letter spacing, text case, decoration, alignment, hyperlink, max lines.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Text node renderer yaz**

```python
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

    # Text or Link
    if hyperlink_url:
        lines.append(f'{prefix}Link("{text}", destination: URL(string: "{hyperlink_url}")!)')
    else:
        lines.append(f'{prefix}Text("{text}")')

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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add _swiftui_text_node with full text styling support"
```

---

### Task 5: `_swiftui_shape_node` - Rectangle, Ellipse, Line rendering

Shape node'ları için tam rendering: fill, stroke, corner radius, shadow, opacity.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Shape node renderer yaz**

```python
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
        corner_radii = _extract_corner_radii(node)
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

    lines.append(f'{prefix}{shape_name}()')
    if fill_code:
        lines.append(f'{prefix}    {fill_code}')

    # Stroke
    stroke_data = _extract_stroke_data(node)
    if stroke_data and stroke_data.get('weight') and stroke_data.get('colors'):
        first_color = stroke_data['colors'][0]
        if first_color.get('type') == 'SOLID':
            hex_c = first_color.get('hex', '#000000')
            rgb = _hex_to_rgb(hex_c)
            weight = stroke_data['weight']
            lines.append(f'{prefix}    .stroke(Color(red: {rgb[0]/255:.3f}, green: {rgb[1]/255:.3f}, blue: {rgb[2]/255:.3f}), lineWidth: {weight})')

    # Frame
    bbox = node.get('absoluteBoundingBox', {})
    w, h = int(bbox.get('width', 0)), int(bbox.get('height', 0))
    if w and h:
        lines.append(f'{prefix}    .frame(width: {w}, height: {h})')

    # Non-uniform corner radius (clip shape)
    corner_radii = _extract_corner_radii(node)
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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add _swiftui_shape_node and _swiftui_vector_node renderers"
```

---

### Task 6: `_swiftui_container_node` - Recursive container rendering

Frame, Group, Component, Instance node'ları VStack/HStack/ZStack olarak render et, children'ı recursive olarak işle.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Container node renderer yaz**

```python
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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add recursive _swiftui_container_node with full layout support"
```

---

### Task 7: `generate_swiftui_code` - Public entry point

Ana public fonksiyonu yaz. Struct wrapper, Preview, RoundedCorner helper shape.

**Files:**
- Modify: `swiftui_generator.py`

**Step 1: Entry point yaz**

```python
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
```

**Step 2: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add swiftui_generator.py
git commit -m "feat: add generate_swiftui_code public entry point with full struct output"
```

---

### Task 8: `figma_mcp.py` entegrasyonu - SwiftUI generator'ı yeni modüle yönlendir

figma_mcp.py'de SwiftUI code generation çağrısını yeni modüle yönlendir. Eski fonksiyonları kaldır.

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Import ekle**

`figma_mcp.py`'nin başına (import bölümüne, ~line 30 civarı) ekle:

```python
from swiftui_generator import generate_swiftui_code as _generate_swiftui_code_v2
```

**Step 2: figma_generate_code fonksiyonunda SwiftUI dalını güncelle**

`figma_generate_code` fonksiyonunda SwiftUI framework seçimini bul (`framework == 'swiftui'` veya benzer koşul). Mevcut `_generate_swiftui_code` çağrısını `_generate_swiftui_code_v2` ile değiştir.

Grep ile bul:
```bash
grep -n "_generate_swiftui_code" figma_mcp.py
```

Bulunan satırı değiştir:
```python
# Eski:
code = _generate_swiftui_code(target_node, component_name)
# Yeni:
code = _generate_swiftui_code_v2(target_node, component_name)
```

**Step 3: Eski SwiftUI fonksiyonlarını kaldır**

`figma_mcp.py`'den şu fonksiyonları sil:
- `_generate_swiftui_code` (line ~3635-3854, ~220 satır)
- `_generate_swiftui_children` (line ~3857-3934, ~78 satır)

Toplam ~298 satır kaldırılacak.

**Step 4: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('OK')"
```

**Step 5: Import kontrolü**

```bash
python -c "from swiftui_generator import generate_swiftui_code; print('Import OK')"
```

**Step 6: Commit**

```bash
git add figma_mcp.py swiftui_generator.py
git commit -m "feat: integrate swiftui_generator module, remove old SwiftUI code from figma_mcp.py"
```

---

### Task 9: Design tokens truncation fix - pagination desteği

Design tokens çıktısı 25K karakteri aştığında truncation yerine kategoriler arasında pagination uygula.

**Files:**
- Modify: `figma_mcp.py:5556-5564` (design tokens truncation bloğu)

**Step 1: Truncation yerine akıllı kısaltma**

Mevcut truncation kodunu bul (line ~5556-5564):

```python
        result = json.dumps(formatted_tokens, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            return json.dumps({
                'truncated': True,
                'message': f'Result exceeded {CHARACTER_LIMIT} characters. Try specifying a node_id to narrow scope.',
                'tokens': {k: v[:10] for k, v in tokens.items()} if tokens else {}
            }, indent=2)
```

Bu bloğu şununla değiştir:

```python
        result = json.dumps(formatted_tokens, indent=2)

        # If result exceeds limit, progressively reduce content
        if len(result) > CHARACTER_LIMIT:
            # Step 1: Remove generated code (CSS/SCSS/Tailwind) - usually the biggest chunk
            if 'generated' in formatted_tokens:
                del formatted_tokens['generated']
                result = json.dumps(formatted_tokens, indent=2)

            # Step 2: If still too large, limit each token category
            if len(result) > CHARACTER_LIMIT:
                max_per_category = 30
                if isinstance(formatted_tokens.get('tokens'), dict):
                    for key in formatted_tokens['tokens']:
                        if isinstance(formatted_tokens['tokens'][key], list) and len(formatted_tokens['tokens'][key]) > max_per_category:
                            total = len(formatted_tokens['tokens'][key])
                            formatted_tokens['tokens'][key] = formatted_tokens['tokens'][key][:max_per_category]
                            formatted_tokens['tokens'][key].append({
                                '_truncated': True,
                                '_message': f'{total - max_per_category} more items. Use node_id to narrow scope.'
                            })
                result = json.dumps(formatted_tokens, indent=2)

            # Step 3: If STILL too large, hard truncate with message
            if len(result) > CHARACTER_LIMIT:
                formatted_tokens['_warning'] = f'Result truncated from {len(result)} chars. Use node_id parameter to narrow scope.'
                # Keep only first 20 of each
                if isinstance(formatted_tokens.get('tokens'), dict):
                    for key in formatted_tokens['tokens']:
                        if isinstance(formatted_tokens['tokens'][key], list):
                            formatted_tokens['tokens'][key] = formatted_tokens['tokens'][key][:20]
                result = json.dumps(formatted_tokens, indent=2)
```

**Step 2: CHARACTER_LIMIT artır**

Line ~72'de:
```python
# Eski:
CHARACTER_LIMIT = 25000
# Yeni:
CHARACTER_LIMIT = 50000
```

**Step 3: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```

**Step 4: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: progressive truncation for design tokens + increase character limit to 50K"
```

---

### Task 10: Final entegrasyon testi + version bump

Tüm değişikliklerin birlikte çalıştığını doğrula, version bump yap.

**Files:**
- Modify: `pyproject.toml`
- Test: tüm dosyalar

**Step 1: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('figma_mcp.py OK')"
python -c "import ast; ast.parse(open('swiftui_generator.py').read()); print('swiftui_generator.py OK')"
```

**Step 2: Import kontrolü**

```bash
python -c "
from swiftui_generator import generate_swiftui_code
from figma_mcp import _generate_swiftui_code_v2
print('All imports OK')
"
```

**Step 3: Fonksiyonel test - mock node ile SwiftUI generation**

```bash
python -c "
from swiftui_generator import generate_swiftui_code

# Mock Figma node tree
mock_node = {
    'type': 'FRAME',
    'name': 'HomeView',
    'layoutMode': 'VERTICAL',
    'itemSpacing': 16,
    'paddingTop': 24, 'paddingRight': 16, 'paddingBottom': 24, 'paddingLeft': 16,
    'absoluteBoundingBox': {'width': 390, 'height': 844, 'x': 0, 'y': 0},
    'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0.98, 'g': 0.98, 'b': 0.98}, 'opacity': 1}],
    'cornerRadius': 0,
    'opacity': 1,
    'children': [
        {
            'type': 'TEXT',
            'name': 'Title',
            'characters': 'Welcome',
            'visible': True,
            'style': {'fontSize': 24, 'fontWeight': 700, 'fontFamily': 'Inter'},
            'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0.1, 'g': 0.1, 'b': 0.1}}],
            'opacity': 1,
            'absoluteBoundingBox': {'width': 200, 'height': 32, 'x': 16, 'y': 24}
        },
        {
            'type': 'FRAME',
            'name': 'Card',
            'layoutMode': 'HORIZONTAL',
            'itemSpacing': 12,
            'paddingTop': 16, 'paddingRight': 16, 'paddingBottom': 16, 'paddingLeft': 16,
            'visible': True,
            'absoluteBoundingBox': {'width': 358, 'height': 80, 'x': 16, 'y': 72},
            'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 1, 'g': 1, 'b': 1}, 'opacity': 1}],
            'cornerRadius': 12,
            'effects': [{'type': 'DROP_SHADOW', 'visible': True, 'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0.1}, 'offset': {'x': 0, 'y': 2}, 'radius': 8, 'spread': 0}],
            'opacity': 1,
            'children': [
                {
                    'type': 'RECTANGLE',
                    'name': 'Avatar',
                    'visible': True,
                    'absoluteBoundingBox': {'width': 48, 'height': 48, 'x': 32, 'y': 88},
                    'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0.4, 'g': 0.6, 'b': 1}}],
                    'cornerRadius': 24,
                    'opacity': 1
                },
                {
                    'type': 'TEXT',
                    'name': 'CardTitle',
                    'characters': 'Daily Goal',
                    'visible': True,
                    'style': {'fontSize': 16, 'fontWeight': 600},
                    'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0.2, 'g': 0.2, 'b': 0.2}}],
                    'opacity': 1,
                    'absoluteBoundingBox': {'width': 200, 'height': 20, 'x': 96, 'y': 88}
                }
            ]
        }
    ]
}

result = generate_swiftui_code(mock_node, 'HomeView')
print(result)

# Verify key elements exist
assert 'VStack' in result, 'Should use VStack for VERTICAL layout'
assert 'HStack' in result, 'Card should use HStack for HORIZONTAL layout'
assert 'Welcome' in result, 'Should include text content'
assert 'Daily Goal' in result, 'Should include nested text'
assert '.cornerRadius(12)' in result or 'cornerRadius: 12' in result, 'Should have corner radius on card'
assert '.shadow(' in result, 'Should have shadow on card'
assert '.padding(' in result, 'Should have padding'
assert 'Inter' in result, 'Should include font family'
assert 'Rectangle()' not in result or '.fill(' in result, 'Rectangles should have fills'
print()
print('ALL ASSERTIONS PASSED')
"
```

**Step 4: Version bump**

`pyproject.toml`'da:
```
version = "2.6.0" → version = "2.7.0"
```

**Step 5: Commit**

```bash
git add figma_mcp.py swiftui_generator.py pyproject.toml
git commit -m "chore: bump version to 2.7.0 - recursive SwiftUI codegen + truncation fix"
```
