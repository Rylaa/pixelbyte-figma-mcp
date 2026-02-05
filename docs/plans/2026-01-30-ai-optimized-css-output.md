# AI-Optimized CSS Output Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** MCP server'ın node detail çıktısına `## CSS Ready` bölümü ekleyerek AI'ın tasarımı doğru koda dönüştürmesini sağlamak.

**Architecture:** Mevcut extraction fonksiyonlarının döndürdüğü verileri kullanan yeni bir `_build_css_ready_section()` fonksiyonu oluşturulacak. Bu fonksiyon node_details dict'ini alacak ve CSS-ready shorthand değerleri üretecek. Markdown çıktısının sonuna (Implementation Hints'ten önce) eklenecek.

**Tech Stack:** Python, mevcut figma_mcp.py helper fonksiyonları

---

### Task 1: `_build_css_ready_background()` helper fonksiyonu

AI'ın en çok hata yaptığı alan renk ve opacity. Fill + node opacity birleştirilecek, CSS-ready background değeri üretilecek.

**Files:**
- Modify: `figma_mcp.py` (yeni fonksiyon, ~line 1870 civarı CSS helpers bölümüne)

**Step 1: Fonksiyonu yaz**

`_extract_fill_data()` çıktısını ve node opacity'yi alıp CSS-ready background değeri döndüren fonksiyon:

```python
def _build_css_ready_background(fills: List[Dict[str, Any]], node_opacity: float = 1.0) -> Optional[str]:
    """Build CSS-ready background property from fills and node opacity."""
    if not fills:
        return None

    css_parts = []
    for fill in fills:
        fill_type = fill.get('fillType', 'SOLID')
        fill_opacity = fill.get('opacity', 1)
        effective_opacity = fill_opacity * node_opacity

        if fill_type == 'SOLID':
            hex_color = fill.get('hex', fill.get('color', '#000000'))
            rgb = _hex_to_rgb(hex_color)
            if effective_opacity < 1:
                css_parts.append(f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {effective_opacity:.2f})")
            else:
                css_parts.append(hex_color)

        elif fill_type.startswith('GRADIENT_'):
            gradient = fill.get('gradient', {})
            stops = gradient.get('stops', [])
            gradient_type = gradient.get('type', 'LINEAR')
            stops_css = []
            for stop in stops:
                stop_hex = stop.get('color', '#000000')
                stop_opacity = stop.get('opacity', 1)
                position = stop.get('position', 0)
                stop_rgb = _hex_to_rgb(stop_hex)
                eff_op = stop_opacity * effective_opacity
                if eff_op < 1:
                    stops_css.append(f"rgba({stop_rgb[0]}, {stop_rgb[1]}, {stop_rgb[2]}, {eff_op:.2f}) {int(position * 100)}%")
                else:
                    stops_css.append(f"{stop_hex} {int(position * 100)}%")

            stops_str = ', '.join(stops_css)
            if gradient_type == 'LINEAR':
                angle = gradient.get('angle', 0)
                css_parts.append(f"linear-gradient({int(angle)}deg, {stops_str})")
            elif gradient_type == 'RADIAL':
                css_parts.append(f"radial-gradient(circle, {stops_str})")
            elif gradient_type == 'ANGULAR':
                css_parts.append(f"conic-gradient({stops_str})")
            elif gradient_type == 'DIAMOND':
                css_parts.append(f"radial-gradient(ellipse, {stops_str})")

    if not css_parts:
        return None
    if len(css_parts) == 1:
        return css_parts[0]
    return ', '.join(css_parts)
```

**Step 2: Test et**

Dosyanın syntax hatası olmadığını doğrula:
```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_background helper for AI-optimized output"
```

---

### Task 2: `_build_css_ready_border()` helper fonksiyonu

Border shorthand: `border: 1px solid #FF0000` + `border-radius: 8px`

**Files:**
- Modify: `figma_mcp.py` (Task 1'den sonraki satıra)

**Step 1: Fonksiyonu yaz**

```python
def _build_css_ready_border(strokes: Optional[Dict[str, Any]], corner_radii: Optional[Dict[str, Any]], node_opacity: float = 1.0) -> Optional[Dict[str, str]]:
    """Build CSS-ready border properties from strokes and corner radii."""
    result = {}

    if strokes:
        weight = strokes.get('weight', 0)
        align = strokes.get('align', 'INSIDE')
        colors = strokes.get('colors', [])
        dashes = strokes.get('dashes', [])

        if weight and colors:
            first_color = colors[0]
            style = 'dashed' if dashes else 'solid'
            color_hex = first_color.get('hex', first_color.get('color', '#000000'))
            color_opacity = first_color.get('opacity', 1)
            effective_opacity = color_opacity * node_opacity

            if effective_opacity < 1:
                rgb = _hex_to_rgb(color_hex)
                color_css = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {effective_opacity:.2f})"
            else:
                color_css = color_hex

            result['border'] = f"{weight}px {style} {color_css}"

            if align == 'INSIDE':
                result['border-style-note'] = 'box-sizing: border-box (stroke inside)'
            elif align == 'OUTSIDE':
                result['border-style-note'] = 'outline recommended (stroke outside)'

        # Individual stroke weights if available
        individual_weights = {}
        for side in ['Top', 'Right', 'Bottom', 'Left']:
            key = f'strokeTop' if side == 'Top' else f'stroke{side}'
            # These come from the raw node, not from extracted strokes
            pass  # Will be handled in extraction enhancement

    if corner_radii:
        tl = corner_radii.get('topLeft', 0)
        tr = corner_radii.get('topRight', 0)
        br = corner_radii.get('bottomRight', 0)
        bl = corner_radii.get('bottomLeft', 0)
        if corner_radii.get('isUniform'):
            result['border-radius'] = f"{int(tl)}px"
        else:
            result['border-radius'] = f"{int(tl)}px {int(tr)}px {int(br)}px {int(bl)}px"

    return result if result else None
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_border helper for border shorthand"
```

---

### Task 3: `_build_css_ready_shadow()` helper fonksiyonu

Shadow shorthand: `box-shadow: 0px 4px 8px 0px rgba(0,0,0,0.1)`

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Fonksiyonu yaz**

```python
def _build_css_ready_shadow(effects: Optional[Dict[str, Any]], node_opacity: float = 1.0) -> Optional[Dict[str, str]]:
    """Build CSS-ready shadow and blur properties from effects."""
    if not effects:
        return None

    result = {}
    shadows = effects.get('shadows', [])
    blurs = effects.get('blurs', [])

    if shadows:
        box_shadows = []
        for shadow in shadows:
            shadow_type = shadow.get('type', 'DROP_SHADOW')
            offset = shadow.get('offset', {'x': 0, 'y': 0})
            radius = shadow.get('radius', 0)
            spread = shadow.get('spread', 0)
            hex_color = shadow.get('hex', shadow.get('color', '#000000'))
            rgb = _hex_to_rgb(hex_color)

            # Shadow color opacity from the color's alpha
            color_str = hex_color
            if 'rgba' in hex_color or node_opacity < 1:
                # Recalculate with effective opacity
                color_str = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {node_opacity:.2f})"
            else:
                # Check if hex has alpha
                if len(hex_color) > 7:  # #RRGGBBAA
                    color_str = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 1)"

            inset = 'inset ' if shadow_type == 'INNER_SHADOW' else ''
            ox = int(offset.get('x', 0))
            oy = int(offset.get('y', 0))
            box_shadows.append(f"{inset}{ox}px {oy}px {int(radius)}px {int(spread)}px {color_str}")

        result['box-shadow'] = ', '.join(box_shadows)

    if blurs:
        for blur in blurs:
            blur_type = blur.get('type', '')
            blur_radius = blur.get('radius', 0)
            if blur_type == 'LAYER_BLUR':
                result['filter'] = f"blur({int(blur_radius)}px)"
            elif blur_type == 'BACKGROUND_BLUR':
                result['backdrop-filter'] = f"blur({int(blur_radius)}px)"

    return result if result else None
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_shadow helper for box-shadow shorthand"
```

---

### Task 4: `_build_css_ready_layout()` helper fonksiyonu

Layout shorthand: `display: flex`, `padding: 24px 32px`, `gap: 16px`, `width/height`

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Fonksiyonu yaz**

```python
def _build_css_ready_layout(auto_layout: Optional[Dict[str, Any]], bounds: Optional[Dict[str, Any]], size_constraints: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Build CSS-ready layout properties from auto-layout, bounds and constraints."""
    result = {}

    if auto_layout:
        mode = auto_layout.get('mode', 'HORIZONTAL')
        result['display'] = 'flex'
        result['flex-direction'] = 'row' if mode == 'HORIZONTAL' else 'column'

        # Gap
        gap = auto_layout.get('gap', 0)
        if gap:
            result['gap'] = f"{int(gap)}px"

        # Padding shorthand
        padding = auto_layout.get('padding', {})
        t = int(padding.get('top', 0))
        r = int(padding.get('right', 0))
        b = int(padding.get('bottom', 0))
        l = int(padding.get('left', 0))
        if t == r == b == l:
            if t > 0:
                result['padding'] = f"{t}px"
        elif t == b and r == l:
            result['padding'] = f"{t}px {r}px"
        else:
            result['padding'] = f"{t}px {r}px {b}px {l}px"

        # Alignment → CSS
        primary = auto_layout.get('primaryAxisAlign', 'MIN')
        counter = auto_layout.get('counterAxisAlign', 'MIN')
        align_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}
        result['justify-content'] = align_map.get(primary, 'flex-start')
        result['align-items'] = align_map.get(counter, 'flex-start')

        # Wrap
        wrap = auto_layout.get('layoutWrap', 'NO_WRAP')
        if wrap == 'WRAP':
            result['flex-wrap'] = 'wrap'

        # Sizing
        primary_sizing = auto_layout.get('primaryAxisSizing', 'AUTO')
        counter_sizing = auto_layout.get('counterAxisSizing', 'AUTO')

        if mode == 'HORIZONTAL':
            if primary_sizing == 'FIXED' and bounds:
                result['width'] = f"{int(bounds.get('width', 0))}px"
            if counter_sizing == 'FIXED' and bounds:
                result['height'] = f"{int(bounds.get('height', 0))}px"
        else:
            if primary_sizing == 'FIXED' and bounds:
                result['height'] = f"{int(bounds.get('height', 0))}px"
            if counter_sizing == 'FIXED' and bounds:
                result['width'] = f"{int(bounds.get('width', 0))}px"

    elif bounds:
        # Non-autolayout: fixed dimensions
        w = bounds.get('width', 0)
        h = bounds.get('height', 0)
        if w:
            result['width'] = f"{int(w)}px"
        if h:
            result['height'] = f"{int(h)}px"

    # Size constraints
    if size_constraints:
        if 'minWidth' in size_constraints:
            result['min-width'] = f"{int(size_constraints['minWidth'])}px"
        if 'maxWidth' in size_constraints:
            result['max-width'] = f"{int(size_constraints['maxWidth'])}px"
        if 'minHeight' in size_constraints:
            result['min-height'] = f"{int(size_constraints['minHeight'])}px"
        if 'maxHeight' in size_constraints:
            result['max-height'] = f"{int(size_constraints['maxHeight'])}px"

    return result if result else None
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_layout helper for flex/padding/sizing"
```

---

### Task 5: `_build_css_ready_typography()` helper fonksiyonu

Font shorthand: `font: 700 16px/24px 'Inter', sans-serif` + text properties

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Fonksiyonu yaz**

```python
def _build_css_ready_typography(text_props: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Build CSS-ready typography properties from text node data."""
    if not text_props:
        return None

    result = {}

    family = text_props.get('fontFamily')
    weight = text_props.get('fontWeight', 400)
    size = text_props.get('fontSize')
    line_height = text_props.get('lineHeight')
    letter_spacing = text_props.get('letterSpacing')
    text_align = text_props.get('textAlign')
    text_case = text_props.get('textCase')
    text_decoration = text_props.get('textDecoration')

    # Font shorthand: weight size/lineHeight family
    if family and size:
        lh_part = f"/{int(line_height)}px" if line_height else ''
        result['font'] = f"{int(weight)} {int(size)}px{lh_part} '{family}', sans-serif"

    # Individual properties (AI can use whichever is clearer)
    if family:
        result['font-family'] = f"'{family}', sans-serif"
    if size:
        result['font-size'] = f"{int(size)}px"
    if weight:
        result['font-weight'] = str(int(weight))
    if line_height:
        result['line-height'] = f"{int(line_height)}px"
    if letter_spacing:
        result['letter-spacing'] = f"{letter_spacing}px"

    # Text alignment
    if text_align:
        align_map = {'LEFT': 'left', 'CENTER': 'center', 'RIGHT': 'right', 'JUSTIFIED': 'justify'}
        css_align = align_map.get(text_align)
        if css_align:
            result['text-align'] = css_align

    # Text transform
    if text_case and text_case != 'ORIGINAL':
        css_case = _text_case_to_css(text_case)
        if css_case:
            result['text-transform'] = css_case

    # Text decoration
    if text_decoration and text_decoration != 'NONE':
        css_dec = _text_decoration_to_css(text_decoration)
        if css_dec:
            result['text-decoration'] = css_dec

    return result if result else None
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_typography helper for font shorthand"
```

---

### Task 6: `_build_css_ready_section()` orchestrator fonksiyonu

Tüm helper'ları birleştirip tek bir CSS Ready section üreten ana fonksiyon.

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Fonksiyonu yaz**

```python
def _build_css_ready_section(node_details: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Build complete CSS-ready properties dict from node details.

    Combines all extracted design properties into CSS shorthand values
    that AI can directly use for code generation.
    """
    css = {}
    node_opacity = node_details.get('opacity', 1)

    # Background/Color
    fills = node_details.get('fills', [])
    bg_css = _build_css_ready_background(fills, node_opacity)
    if bg_css:
        # For text nodes, use 'color'; for others, use 'background'
        if node_details.get('type') == 'TEXT':
            css['color'] = bg_css
        else:
            css['background'] = bg_css

    # Opacity (only if not 1, and not already folded into color)
    if node_opacity < 1:
        css['opacity'] = f"{node_opacity}"

    # Border
    border_css = _build_css_ready_border(
        node_details.get('strokes'),
        node_details.get('cornerRadius'),
        node_opacity
    )
    if border_css:
        css.update(border_css)

    # Shadow & Blur
    shadow_css = _build_css_ready_shadow(
        node_details.get('effects'),
        node_opacity
    )
    if shadow_css:
        css.update(shadow_css)

    # Layout
    layout_css = _build_css_ready_layout(
        node_details.get('autoLayout'),
        node_details.get('bounds'),
        node_details.get('sizeConstraints')
    )
    if layout_css:
        css.update(layout_css)

    # Typography
    typography_css = _build_css_ready_typography(
        node_details.get('text')
    )
    if typography_css:
        css.update(typography_css)

    # Transform
    transform = node_details.get('transform', {})
    transform_css = _transform_to_css_from_details(transform)
    if transform_css:
        css['transform'] = transform_css

    # Overflow (clip content)
    if node_details.get('clipsContent'):
        css['overflow'] = 'hidden'

    # Blend mode
    blend_mode = node_details.get('blendMode')
    if blend_mode:
        css_blend = _blend_mode_to_css(blend_mode)
        if css_blend:
            css['mix-blend-mode'] = css_blend

    return css if css else None


def _transform_to_css_from_details(transform: Dict[str, Any]) -> Optional[str]:
    """Convert extracted transform details to CSS transform string."""
    parts = []
    rotation = transform.get('rotation', 0)
    if rotation:
        angle_deg = -rotation * (180 / 3.14159265359)
        if abs(angle_deg) > 0.1:
            parts.append(f"rotate({angle_deg:.1f}deg)")
    return ' '.join(parts) if parts else None
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add _build_css_ready_section orchestrator combining all CSS helpers"
```

---

### Task 7: Markdown çıktısına `## CSS Ready` bölümü ekle

`figma_get_node_details` tool'unun markdown çıktısına CSS Ready section'ı ekle. Implementation Hints'ten hemen önce yerleşecek.

**Files:**
- Modify: `figma_mcp.py:4890-4895` (Text Properties bölümünden sonra, Implementation Hints'ten önce)

**Step 1: CSS Ready bölümünü markdown'a ekle**

`figma_mcp.py` içinde, line ~4890'dan sonra (Text Properties `lines.append("")` satırından sonra), Implementation Hints bölümünden önce şu kodu ekle:

```python
        # CSS Ready Section
        css_ready = _build_css_ready_section(node_details)
        if css_ready:
            lines.append("## 🎨 CSS Ready")
            lines.append("```css")
            # Remove notes from CSS output
            css_props = {k: v for k, v in css_ready.items() if not k.endswith('-note')}
            for prop, value in css_props.items():
                lines.append(f"  {prop}: {value};")
            lines.append("```")
            # Add notes as comments
            notes = {k: v for k, v in css_ready.items() if k.endswith('-note')}
            for note_key, note_value in notes.items():
                lines.append(f"> ℹ️ {note_value}")
            lines.append("")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add CSS Ready section to node details markdown output"
```

---

### Task 8: `_extract_stroke_data()` fonksiyonuna individual stroke weights ekle

Figma'da node'ların `strokeTopWeight`, `strokeBottomWeight`, `strokeLeftWeight`, `strokeRightWeight` özellikleri olabilir. Bunları extract et.

**Files:**
- Modify: `figma_mcp.py:740-749` (`_extract_stroke_data` return bloğu)

**Step 1: Individual stroke weights ekle**

`_extract_stroke_data` fonksiyonunun return dict'ine ekle:

```python
    # Check for individual stroke weights
    individual_weights = {}
    for side, key in [('top', 'strokeTopWeight'), ('right', 'strokeRightWeight'),
                       ('bottom', 'strokeBottomWeight'), ('left', 'strokeLeftWeight')]:
        if key in node:
            individual_weights[side] = node[key]

    result = {
        'colors': stroke_colors,
        'weight': node.get('strokeWeight', 1),
        'align': node.get('strokeAlign', 'INSIDE'),
        'cap': node.get('strokeCap', 'NONE'),
        'join': node.get('strokeJoin', 'MITER'),
        'miterLimit': node.get('strokeMiterLimit', 4),
        'dashes': node.get('strokeDashes', []),
        'dashCap': node.get('strokeDashCap', 'NONE')
    }

    if individual_weights:
        result['individualWeights'] = individual_weights

    return result
```

**Step 2: `_build_css_ready_border()` fonksiyonunu güncelle**

Individual weights varsa per-side border CSS üret:

Fonksiyona, `result['border'] = ...` satırından sonra ekle:

```python
            # Check for individual stroke weights
            ind_weights = strokes.get('individualWeights')
            if ind_weights:
                for side, w in ind_weights.items():
                    result[f'border-{side}'] = f"{w}px {style} {color_css}"
```

**Step 3: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: extract individual stroke weights for per-side border CSS"
```

---

### Task 9: Effective opacity hesaplamasını fill markdown çıktısına ekle

Mevcut fill bölümündeki çıktıya effective opacity bilgisini ekle (node opacity x fill opacity).

**Files:**
- Modify: `figma_mcp.py:4716-4736` (Fills markdown bölümü)

**Step 1: Effective opacity'yi fill çıktısına ekle**

Fills bölümünde, solid fill satırını güncelle:

Mevcut:
```python
lines.append(f"- **Solid:** {fill.get('color')} (opacity: {fill.get('opacity', 1):.2f})")
```

Yeni:
```python
fill_op = fill.get('opacity', 1)
node_op = node_details.get('opacity', 1)
effective_op = fill_op * node_op
opacity_info = f"opacity: {fill_op:.2f}"
if node_op < 1:
    opacity_info += f" × node:{node_op:.2f} = effective:{effective_op:.2f}"
lines.append(f"- **Solid:** {fill.get('color')} ({opacity_info})")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: show effective opacity (node × fill) in fills markdown output"
```

---

### Task 10: Shadow markdown çıktısına CSS shorthand ekle

Mevcut shadow bölümündeki çıktının yanına CSS shorthand'i de ekle.

**Files:**
- Modify: `figma_mcp.py:4770-4783` (Effects markdown bölümü)

**Step 1: Shadow satırının yanına CSS shorthand ekle**

Effects bölümünü güncelle:

```python
        # Effects
        if 'effects' in node_details:
            lines.append("## Effects")
            if node_details['effects'].get('shadows'):
                for shadow in node_details['effects']['shadows']:
                    offset = shadow['offset']
                    hex_color = shadow.get('hex', shadow.get('color', '#000000'))
                    rgb = _hex_to_rgb(hex_color)
                    ox = int(offset.get('x', 0))
                    oy = int(offset.get('y', 0))
                    radius = int(shadow['radius'])
                    spread = int(shadow['spread'])
                    inset = 'inset ' if shadow['type'] == 'INNER_SHADOW' else ''

                    lines.append(
                        f"- **{shadow['type']}:** {hex_color}, "
                        f"offset ({ox}, {oy}), "
                        f"blur {radius}px, spread {spread}px"
                    )
                    lines.append(
                        f"  - `box-shadow: {inset}{ox}px {oy}px {radius}px {spread}px {hex_color};`"
                    )
            if node_details['effects'].get('blurs'):
                for blur in node_details['effects']['blurs']:
                    blur_type = blur['type']
                    blur_radius = int(blur['radius'])
                    lines.append(f"- **{blur_type}:** {blur_radius}px")
                    if blur_type == 'LAYER_BLUR':
                        lines.append(f"  - `filter: blur({blur_radius}px);`")
                    elif blur_type == 'BACKGROUND_BLUR':
                        lines.append(f"  - `backdrop-filter: blur({blur_radius}px);`")
            lines.append("")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add inline CSS shorthand to shadow/blur markdown output"
```

---

### Task 11: Auto-layout markdown çıktısına CSS shorthand ekle

Padding, gap, alignment gibi değerlerin CSS karşılıklarını inline olarak göster.

**Files:**
- Modify: `figma_mcp.py:4786-4800` (Auto Layout markdown bölümü)

**Step 1: CSS karşılıklarını inline ekle**

```python
        # Auto-layout
        if 'autoLayout' in node_details:
            al = node_details['autoLayout']
            mode = al['mode']
            direction = 'row' if mode == 'HORIZONTAL' else 'column'

            # Padding shorthand
            p = al['padding']
            t, r, b, l = int(p['top']), int(p['right']), int(p['bottom']), int(p['left'])
            if t == r == b == l:
                padding_css = f"{t}px" if t > 0 else "0"
            elif t == b and r == l:
                padding_css = f"{t}px {r}px"
            else:
                padding_css = f"{t}px {r}px {b}px {l}px"

            align_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}

            lines.extend([
                "## Auto Layout",
                f"- **Direction:** {mode} → `flex-direction: {direction}`",
                f"- **Gap:** {al['gap']}px → `gap: {int(al['gap'])}px`",
                f"- **Padding:** T:{t} R:{r} B:{b} L:{l} → `padding: {padding_css}`",
                f"- **Primary Align:** {al['primaryAxisAlign']} → `justify-content: {align_map.get(al['primaryAxisAlign'], 'flex-start')}`",
                f"- **Counter Align:** {al['counterAxisAlign']} → `align-items: {align_map.get(al['counterAxisAlign'], 'flex-start')}`",
                f"- **Primary Sizing:** {al['primaryAxisSizing']}",
                f"- **Counter Sizing:** {al['counterAxisSizing']}",
            ])
            if al.get('layoutWrap') != 'NO_WRAP':
                lines.append(f"- **Wrap:** {al['layoutWrap']} → `flex-wrap: wrap`")
            lines.append("")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add inline CSS equivalents to auto-layout markdown output"
```

---

### Task 12: Stroke markdown çıktısına CSS border shorthand ekle

**Files:**
- Modify: `figma_mcp.py:4738-4752` (Strokes markdown bölümü)

**Step 1: Border CSS shorthand satırı ekle**

```python
        # Strokes
        if 'strokes' in node_details:
            s = node_details['strokes']
            weight = s['weight']
            dashes = s.get('dashes', [])
            style = 'dashed' if dashes else 'solid'

            lines.append("## Strokes")
            lines.append(f"- **Weight:** {weight}px")
            lines.append(f"- **Align:** {s['align']}")
            lines.append(f"- **Cap:** {s['cap']}, **Join:** {s['join']}")
            if dashes:
                lines.append(f"- **Dashes:** {dashes}")

            # Individual weights
            if s.get('individualWeights'):
                iw = s['individualWeights']
                lines.append(f"- **Individual Weights:** T:{iw.get('top', weight)} R:{iw.get('right', weight)} B:{iw.get('bottom', weight)} L:{iw.get('left', weight)}")

            for color in s.get('colors', []):
                if color.get('type') == 'SOLID':
                    hex_c = color.get('hex', color.get('color'))
                    lines.append(f"- **Color:** {hex_c}")
                    lines.append(f"  - `border: {weight}px {style} {hex_c};`")
                elif color.get('type', '').startswith('GRADIENT_'):
                    lines.append(f"- **Gradient stroke**")
            lines.append("")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add inline CSS border shorthand to stroke markdown output"
```

---

### Task 13: Text properties markdown çıktısına CSS font shorthand ekle

**Files:**
- Modify: `figma_mcp.py:4868-4890` (Text Properties markdown bölümü)

**Step 1: Font CSS shorthand satırı ekle**

Text Properties bölümünün sonuna (son `lines.append("")`'dan önce) ekle:

```python
            # CSS font shorthand
            if txt.get('fontFamily') and txt.get('fontSize'):
                weight = int(txt.get('fontWeight', 400))
                size = int(txt['fontSize'])
                lh = f"/{int(txt['lineHeight'])}px" if txt.get('lineHeight') else ''
                family = txt['fontFamily']
                lines.append(f"- **CSS:** `font: {weight} {size}px{lh} '{family}', sans-serif;`")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add CSS font shorthand to text properties markdown output"
```

---

### Task 14: Fill markdown çıktısına CSS background shorthand ekle

**Files:**
- Modify: `figma_mcp.py:4716-4736` (Fills markdown bölümü, Task 9'dan sonra)

**Step 1: Background CSS satırı ekle**

Fills bölümünün sonuna (`lines.append("")`'dan önce) CSS background satırını ekle:

```python
            # CSS background shorthand for fills section
            node_op = node_details.get('opacity', 1)
            bg_css = _build_css_ready_background(node_details['fills'], node_op)
            if bg_css:
                prop_name = 'color' if node_details.get('type') == 'TEXT' else 'background'
                lines.append(f"- **CSS:** `{prop_name}: {bg_css};`")
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add CSS background shorthand to fills markdown output"
```

---

### Task 15: Corner radius markdown çıktısına CSS shorthand ekle

**Files:**
- Modify: `figma_mcp.py:4754-4767` (Corner radius markdown bölümü)

**Step 1: CSS shorthand ekle**

```python
        # Corner radius
        if 'cornerRadius' in node_details:
            cr = node_details['cornerRadius']
            tl = int(cr.get('topLeft', 0))
            tr = int(cr.get('topRight', 0))
            br = int(cr.get('bottomRight', 0))
            bl = int(cr.get('bottomLeft', 0))

            if cr.get('isUniform'):
                css_val = f"{tl}px"
            else:
                css_val = f"{tl}px {tr}px {br}px {bl}px"

            if cr.get('isUniform'):
                lines.append(f"## Border Radius: {tl}px → `border-radius: {css_val}`\n")
            else:
                lines.extend([
                    "## Border Radius",
                    f"- **Top Left:** {tl}px, **Top Right:** {tr}px, **Bottom Right:** {br}px, **Bottom Left:** {bl}px",
                    f"- `border-radius: {css_val}`",
                    ""
                ])
```

**Step 2: Test et**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: add CSS border-radius shorthand to corner radius output"
```

---

### Task 16: Final entegrasyon testi

Tüm değişikliklerin birlikte çalıştığını doğrula.

**Files:**
- Read: `figma_mcp.py` (tüm değişiklikler)

**Step 1: Syntax kontrolü**

```bash
python -c "import ast; ast.parse(open('figma_mcp.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

**Step 2: Import kontrolü**

```bash
python -c "import figma_mcp; print('Import OK')"
```
Expected: `Import OK`

**Step 3: Yeni fonksiyonların varlığını doğrula**

```bash
python -c "
from figma_mcp import (
    _build_css_ready_background,
    _build_css_ready_border,
    _build_css_ready_shadow,
    _build_css_ready_layout,
    _build_css_ready_typography,
    _build_css_ready_section,
    _transform_to_css_from_details
)
print('All functions imported OK')
"
```
Expected: `All functions imported OK`

**Step 4: Final commit**

```bash
git add figma_mcp.py
git commit -m "feat: complete AI-optimized CSS output - all helpers integrated"
```
