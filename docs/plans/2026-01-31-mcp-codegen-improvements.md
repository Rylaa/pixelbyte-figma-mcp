# MCP Code Generation - Modular Architecture & Full Property Support

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tum code generator'lari `generators/` modulu altinda ayristirmak, ortak helper'lari paylasimli base modulu olusturmak, ve findings doc'taki tum P0/P1 sorunlari cozmek (recursive traversal, multi-fill, gradient turleri, typography, blur, stroke).

**Architecture:** `figma_mcp.py`'den (6332 satir) code generation fonksiyonlarini ayri modullere tasiyoruz. `generators/base.py` ortak dataclass'lar ve helper'lar barindiracak. Her framework kendi generator dosyasini alacak. React'taki `_recursive_node_to_jsx` (satir 3964) referans pattern. Mevcut `_get_background_css` (satir 2261) multi-fill destegini zaten CSS icin cozmus - bunu framework-agnostic hale getiriyoruz.

**Tech Stack:** Python 3.10+, dataclasses, mevcut figma_mcp.py helper'lari, Figma REST API

**Kaynak Bulgular:** `/Users/yusufdemirkoparan/Projects/pixelbyte-agent-workflows/docs/mcp-code-gen-findings.md`

---

## Mevcut Durum Ozeti

### Dosya Yapisi
```
figma_mcp.py           (6332 satir - monolitik)
swiftui_generator.py   (745 satir - yeni, ayri modul)
```

### Generator Olgunluk Seviyeleri
| Generator | Recursive | Multi-Fill | Gradients | Typography | Blur | Stroke |
|-----------|-----------|------------|-----------|------------|------|--------|
| React (`_recursive_node_to_jsx`, L:3964) | Evet (depth unlimited, 20 child limit) | Evet (`_get_background_css`) | LINEAR, RADIAL, ANGULAR, DIAMOND via CSS | Tam | CSS filter | Tam |
| Vue (`_recursive_node_to_vue_template`) | Evet | Evet | Ayni CSS | Tam | CSS filter | Tam |
| CSS/SCSS | Evet | Evet | Ayni CSS | Tam | CSS filter | Tam |
| SwiftUI (`swiftui_generator.py`) | Evet (depth 8, 10 child limit) | HAYIR (ilk fill'de break) | LINEAR + RADIAL only | Kismi (gradient text yok) | LAYER only | Solid only |
| Kotlin (`_generate_kotlin_code`, L:3635) | HAYIR | HAYIR | Kismi | Kismi | Kismi | Kismi |

### Kritik Helper'lar (figma_mcp.py'de)
- `_rgba_to_hex` (L:545), `_hex_to_rgb` (L:557), `_rgb_to_hsl` (L:575)
- `_extract_fill_data` (L:644), `_extract_stroke_data` (L:702)
- `_extract_corner_radii` (L:764), `_extract_effects_data` (L:1395)
- `_extract_auto_layout` (L:1445)
- `_gradient_to_css` (L:1740), `_get_background_css` (L:2261)
- `_get_single_fill_css` (L:2216)
- `_calculate_gradient_angle` (L:613), `_extract_gradient_stops` (L:631)
- `SWIFTUI_WEIGHT_MAP` (L:93), `KOTLIN_WEIGHT_MAP` (L:106), `TAILWIND_WEIGHT_MAP` (L:80)

### Test Durumu
- Projede hicbir test dosyasi yok. Test altyapisi kurulmali.

---

## Task 1: `generators/` paket yapisini olustur

**Files:**
- Create: `generators/__init__.py`
- Create: `generators/base.py`

**Step 1: Dizin ve init dosyasi olustur**

```bash
mkdir -p generators
```

```python
# generators/__init__.py
"""Pixelbyte Figma MCP - Code Generators Package."""
```

**Step 2: `generators/base.py` temel yapisini olustur**

Ortak dataclass'lar ve color utility'leri. `figma_mcp.py`'den `_rgba_to_hex` (L:545-554), `_hex_to_rgb` (L:557-572), `_rgb_to_hsl` (L:575-594), `_calculate_luminance` (L:597-603), `_contrast_ratio` (L:605-610) fonksiyonlarini kopyala.

```python
# generators/base.py
"""
Shared utilities and data structures for all code generators.

Provides: color conversion, gradient parsing, fill/stroke extraction,
layout info, typography info - framework-agnostic intermediate representations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import math


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CHILDREN_LIMIT = 20       # React/Vue/CSS child limit per container
MAX_NATIVE_CHILDREN_LIMIT = 10  # SwiftUI/Kotlin child limit
MAX_DEPTH = 8                  # Max recursive depth

SWIFTUI_WEIGHT_MAP = {
    100: '.ultraLight', 200: '.thin', 300: '.light', 400: '.regular',
    500: '.medium', 600: '.semibold', 700: '.bold', 800: '.heavy', 900: '.black'
}

KOTLIN_WEIGHT_MAP = {
    100: 'FontWeight.Thin', 200: 'FontWeight.ExtraLight', 300: 'FontWeight.Light',
    400: 'FontWeight.Normal', 500: 'FontWeight.Medium', 600: 'FontWeight.SemiBold',
    700: 'FontWeight.Bold', 800: 'FontWeight.ExtraBold', 900: 'FontWeight.Black'
}

TAILWIND_WEIGHT_MAP = {
    100: 'font-thin', 200: 'font-extralight', 300: 'font-light',
    400: 'font-normal', 500: 'font-medium', 600: 'font-semibold',
    700: 'font-bold', 800: 'font-extrabold', 900: 'font-black'
}

TAILWIND_ALIGN_MAP = {
    'LEFT': 'text-left', 'CENTER': 'text-center',
    'RIGHT': 'text-right', 'JUSTIFIED': 'text-justify'
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ColorValue:
    """Framework-agnostic color representation."""
    r: float  # 0-1 range (Figma native)
    g: float
    b: float
    a: float = 1.0

    @property
    def hex(self) -> str:
        ri, gi, bi = int(self.r * 255), int(self.g * 255), int(self.b * 255)
        if self.a < 1:
            return f"rgba({ri}, {gi}, {bi}, {self.a:.2f})"
        return f"#{ri:02x}{gi:02x}{bi:02x}"

    @property
    def rgb_ints(self) -> Tuple[int, int, int]:
        return int(self.r * 255), int(self.g * 255), int(self.b * 255)

    @classmethod
    def from_figma(cls, color: Dict[str, float], opacity: float = 1.0) -> 'ColorValue':
        return cls(
            r=color.get('r', 0), g=color.get('g', 0), b=color.get('b', 0),
            a=opacity if opacity < 1 else color.get('a', 1.0)
        )


@dataclass
class GradientStop:
    """Single gradient color stop."""
    color: ColorValue
    position: float  # 0-1


@dataclass
class GradientDef:
    """Framework-agnostic gradient definition."""
    type: str  # LINEAR, RADIAL, ANGULAR, DIAMOND
    stops: List[GradientStop]
    handle_positions: List[Dict[str, float]] = field(default_factory=list)
    opacity: float = 1.0

    @property
    def angle_degrees(self) -> float:
        """Calculate CSS angle from handle positions (for LINEAR)."""
        if len(self.handle_positions) < 2:
            return 180.0
        start = self.handle_positions[0]
        end = self.handle_positions[1]
        dx = end.get('x', 1) - start.get('x', 0)
        dy = end.get('y', 1) - start.get('y', 0)
        angle = math.degrees(math.atan2(dy, dx))
        return (90 - angle) % 360


@dataclass
class FillLayer:
    """Single fill layer. A node can have multiple fills stacked."""
    type: str  # SOLID, GRADIENT_LINEAR, GRADIENT_RADIAL, GRADIENT_ANGULAR, GRADIENT_DIAMOND, IMAGE
    color: Optional[ColorValue] = None
    gradient: Optional[GradientDef] = None
    image_ref: Optional[str] = None
    scale_mode: str = 'FILL'  # FILL, FIT, TILE, STRETCH
    opacity: float = 1.0
    visible: bool = True


@dataclass
class StrokeInfo:
    """Framework-agnostic stroke definition."""
    weight: float
    colors: List[FillLayer]  # Can be solid or gradient
    align: str = 'INSIDE'  # INSIDE, CENTER, OUTSIDE
    cap: str = 'NONE'
    join: str = 'MITER'
    dashes: List[float] = field(default_factory=list)
    individual_weights: Optional[Dict[str, float]] = None  # top, right, bottom, left


@dataclass
class CornerRadii:
    """Corner radius values."""
    top_left: float = 0
    top_right: float = 0
    bottom_right: float = 0
    bottom_left: float = 0

    @property
    def is_uniform(self) -> bool:
        return self.top_left == self.top_right == self.bottom_right == self.bottom_left

    @property
    def uniform_value(self) -> float:
        return self.top_left


@dataclass
class ShadowEffect:
    """Shadow effect."""
    type: str  # DROP_SHADOW, INNER_SHADOW
    color: ColorValue
    offset_x: float = 0
    offset_y: float = 0
    radius: float = 0
    spread: float = 0


@dataclass
class BlurEffect:
    """Blur effect."""
    type: str  # LAYER_BLUR, BACKGROUND_BLUR
    radius: float = 0


@dataclass
class LayoutInfo:
    """Auto-layout information."""
    mode: str  # VERTICAL, HORIZONTAL, NONE
    gap: float = 0
    padding_top: float = 0
    padding_right: float = 0
    padding_bottom: float = 0
    padding_left: float = 0
    primary_align: str = 'MIN'  # MIN, CENTER, MAX, SPACE_BETWEEN
    counter_align: str = 'MIN'  # MIN, CENTER, MAX
    primary_sizing: str = 'AUTO'  # AUTO, FIXED
    counter_sizing: str = 'AUTO'
    wrap: str = 'NO_WRAP'  # NO_WRAP, WRAP


@dataclass
class TextStyle:
    """Typography information."""
    font_family: str = ''
    font_size: float = 16
    font_weight: int = 400
    line_height: Optional[float] = None
    letter_spacing: float = 0
    text_align: str = 'LEFT'
    text_case: str = 'ORIGINAL'  # ORIGINAL, UPPER, LOWER, TITLE
    text_decoration: str = 'NONE'  # NONE, UNDERLINE, STRIKETHROUGH
    color: Optional[ColorValue] = None
    gradient: Optional[GradientDef] = None  # For gradient text fills
    max_lines: Optional[int] = None
    truncation: str = 'DISABLED'


@dataclass
class StyleBundle:
    """Complete style information for a node."""
    fills: List[FillLayer] = field(default_factory=list)
    stroke: Optional[StrokeInfo] = None
    corners: Optional[CornerRadii] = None
    shadows: List[ShadowEffect] = field(default_factory=list)
    blurs: List[BlurEffect] = field(default_factory=list)
    opacity: float = 1.0
    blend_mode: str = 'PASS_THROUGH'
    rotation: float = 0
    layout: Optional[LayoutInfo] = None
    width: float = 0
    height: float = 0
    clips_content: bool = False


# ---------------------------------------------------------------------------
# Color Conversion Helpers
# ---------------------------------------------------------------------------

def rgba_to_hex(color: Dict[str, float]) -> str:
    """Convert Figma color dict (r,g,b,a in 0-1) to hex string."""
    r = int(color.get('r', 0) * 255)
    g = int(color.get('g', 0) * 255)
    b = int(color.get('b', 0) * 255)
    a = color.get('a', 1)
    if a < 1:
        return f"rgba({r}, {g}, {b}, {a:.2f})"
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple (0-255)."""
    hex_color = hex_color.strip()
    if hex_color.startswith('rgba'):
        parts = hex_color.replace('rgba(', '').replace(')', '').split(',')
        return int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    if len(hex_color) >= 6:
        return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return 0, 0, 0


# ---------------------------------------------------------------------------
# Figma Node → Dataclass Parsers
# ---------------------------------------------------------------------------

def parse_fills(node: Dict[str, Any]) -> List[FillLayer]:
    """Parse all fills from a Figma node into FillLayer list."""
    fills = node.get('fills', [])
    result = []
    for fill in fills:
        visible = fill.get('visible', True)
        if not visible:
            continue
        fill_type = fill.get('type', '')
        layer = FillLayer(type=fill_type, visible=visible, opacity=fill.get('opacity', 1.0))

        if fill_type == 'SOLID':
            color_data = fill.get('color', {})
            layer.color = ColorValue.from_figma(color_data, fill.get('opacity', 1.0))

        elif 'GRADIENT' in fill_type:
            stops = []
            for s in fill.get('gradientStops', []):
                c = s.get('color', {})
                stops.append(GradientStop(
                    color=ColorValue(r=c.get('r', 0), g=c.get('g', 0), b=c.get('b', 0), a=c.get('a', 1)),
                    position=s.get('position', 0)
                ))
            gradient_type = fill_type.replace('GRADIENT_', '')
            layer.gradient = GradientDef(
                type=gradient_type,
                stops=stops,
                handle_positions=fill.get('gradientHandlePositions', []),
                opacity=fill.get('opacity', 1.0)
            )

        elif fill_type == 'IMAGE':
            layer.image_ref = fill.get('imageRef', '')
            layer.scale_mode = fill.get('scaleMode', 'FILL')

        result.append(layer)
    return result


def parse_stroke(node: Dict[str, Any]) -> Optional[StrokeInfo]:
    """Parse stroke from a Figma node."""
    strokes = node.get('strokes', [])
    weight = node.get('strokeWeight', 0)
    if not strokes or weight == 0:
        return None

    colors = []
    for s in strokes:
        if not s.get('visible', True):
            continue
        s_type = s.get('type', '')
        layer = FillLayer(type=s_type, visible=True, opacity=s.get('opacity', 1.0))
        if s_type == 'SOLID':
            layer.color = ColorValue.from_figma(s.get('color', {}), s.get('opacity', 1.0))
        elif 'GRADIENT' in s_type:
            stops = []
            for gs in s.get('gradientStops', []):
                c = gs.get('color', {})
                stops.append(GradientStop(
                    color=ColorValue(r=c.get('r', 0), g=c.get('g', 0), b=c.get('b', 0), a=c.get('a', 1)),
                    position=gs.get('position', 0)
                ))
            layer.gradient = GradientDef(
                type=s_type.replace('GRADIENT_', ''),
                stops=stops,
                handle_positions=s.get('gradientHandlePositions', []),
                opacity=s.get('opacity', 1.0)
            )
        colors.append(layer)

    if not colors:
        return None

    dashes = node.get('strokeDashes', [])
    individual = None
    iw = node.get('individualStrokeWeights')
    if iw:
        individual = {'top': iw.get('top', 0), 'right': iw.get('right', 0),
                       'bottom': iw.get('bottom', 0), 'left': iw.get('left', 0)}

    return StrokeInfo(
        weight=weight, colors=colors,
        align=node.get('strokeAlign', 'INSIDE'),
        cap=node.get('strokeCap', 'NONE'),
        join=node.get('strokeJoin', 'MITER'),
        dashes=dashes,
        individual_weights=individual
    )


def parse_corners(node: Dict[str, Any]) -> Optional[CornerRadii]:
    """Parse corner radii from a Figma node."""
    radii = node.get('rectangleCornerRadii')
    if radii and len(radii) == 4:
        return CornerRadii(top_left=radii[0], top_right=radii[1],
                          bottom_right=radii[2], bottom_left=radii[3])
    cr = node.get('cornerRadius', 0)
    if cr > 0:
        return CornerRadii(top_left=cr, top_right=cr, bottom_right=cr, bottom_left=cr)
    return None


def parse_effects(node: Dict[str, Any]) -> Tuple[List[ShadowEffect], List[BlurEffect]]:
    """Parse effects (shadows + blurs) from a Figma node."""
    effects = node.get('effects', [])
    shadows = []
    blurs = []
    for e in effects:
        if not e.get('visible', True):
            continue
        e_type = e.get('type', '')
        if e_type in ('DROP_SHADOW', 'INNER_SHADOW'):
            color = e.get('color', {})
            offset = e.get('offset', {'x': 0, 'y': 0})
            shadows.append(ShadowEffect(
                type=e_type,
                color=ColorValue(r=color.get('r', 0), g=color.get('g', 0),
                                b=color.get('b', 0), a=color.get('a', 0.25)),
                offset_x=offset.get('x', 0), offset_y=offset.get('y', 0),
                radius=e.get('radius', 0), spread=e.get('spread', 0)
            ))
        elif e_type in ('LAYER_BLUR', 'BACKGROUND_BLUR'):
            blurs.append(BlurEffect(type=e_type, radius=e.get('radius', 0)))
    return shadows, blurs


def parse_layout(node: Dict[str, Any]) -> Optional[LayoutInfo]:
    """Parse auto-layout from a Figma node."""
    mode = node.get('layoutMode')
    if not mode or mode == 'NONE':
        return None
    return LayoutInfo(
        mode=mode,
        gap=node.get('itemSpacing', 0),
        padding_top=node.get('paddingTop', 0),
        padding_right=node.get('paddingRight', 0),
        padding_bottom=node.get('paddingBottom', 0),
        padding_left=node.get('paddingLeft', 0),
        primary_align=node.get('primaryAxisAlignItems', 'MIN'),
        counter_align=node.get('counterAxisAlignItems', 'MIN'),
        primary_sizing=node.get('primaryAxisSizingMode', 'AUTO'),
        counter_sizing=node.get('counterAxisSizingMode', 'AUTO'),
        wrap=node.get('layoutWrap', 'NO_WRAP')
    )


def parse_text_style(node: Dict[str, Any]) -> TextStyle:
    """Parse text styling from a TEXT node."""
    style = node.get('style', {})
    fills = node.get('fills', [])

    # Text color: check for solid or gradient
    text_color = None
    text_gradient = None
    for fill in fills:
        if not fill.get('visible', True):
            continue
        if fill.get('type') == 'SOLID':
            text_color = ColorValue.from_figma(fill.get('color', {}), fill.get('opacity', 1.0))
            break
        elif 'GRADIENT' in fill.get('type', ''):
            stops = []
            for s in fill.get('gradientStops', []):
                c = s.get('color', {})
                stops.append(GradientStop(
                    color=ColorValue(r=c.get('r', 0), g=c.get('g', 0), b=c.get('b', 0), a=c.get('a', 1)),
                    position=s.get('position', 0)
                ))
            text_gradient = GradientDef(
                type=fill['type'].replace('GRADIENT_', ''),
                stops=stops,
                handle_positions=fill.get('gradientHandlePositions', []),
                opacity=fill.get('opacity', 1.0)
            )
            break

    return TextStyle(
        font_family=style.get('fontFamily', ''),
        font_size=style.get('fontSize', 16),
        font_weight=style.get('fontWeight', 400),
        line_height=style.get('lineHeightPx'),
        letter_spacing=style.get('letterSpacing', 0),
        text_align=style.get('textAlignHorizontal', 'LEFT'),
        text_case=style.get('textCase', 'ORIGINAL'),
        text_decoration=style.get('textDecoration', 'NONE'),
        color=text_color,
        gradient=text_gradient,
        max_lines=style.get('maxLines'),
        truncation=style.get('textTruncation', 'DISABLED')
    )


def parse_style_bundle(node: Dict[str, Any]) -> StyleBundle:
    """Parse complete style information from a Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    shadows, blurs = parse_effects(node)

    return StyleBundle(
        fills=parse_fills(node),
        stroke=parse_stroke(node),
        corners=parse_corners(node),
        shadows=shadows,
        blurs=blurs,
        opacity=node.get('opacity', 1.0),
        blend_mode=node.get('blendMode', 'PASS_THROUGH'),
        rotation=node.get('rotation', 0),
        layout=parse_layout(node),
        width=bbox.get('width', 0),
        height=bbox.get('height', 0),
        clips_content=node.get('clipsContent', False)
    )
```

**Step 3: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/base.py').read()); print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add generators/__init__.py generators/base.py
git commit -m "feat: create generators package with shared base module and dataclasses"
```

---

## Task 2: SwiftUI generator'i `generators/` altina tasi ve base.py'yi kullanacak sekilde guncelle

**Files:**
- Move: `swiftui_generator.py` → `generators/swiftui_generator.py`
- Modify: `generators/swiftui_generator.py` (import'lari guncelle, base dataclass'larini kullan)
- Modify: `figma_mcp.py` (import path'i guncelle)

**Step 1: Dosyayi tasi**

```bash
mv swiftui_generator.py generators/swiftui_generator.py
```

**Step 2: Import'lari guncelle**

`generators/swiftui_generator.py`'nin basindaki import'lari degistir:

Eski:
```python
from figma_mcp import (
    _hex_to_rgb,
    _extract_stroke_data,
    _extract_effects_data,
    _extract_corner_radii,
    SWIFTUI_WEIGHT_MAP,
    MAX_NATIVE_CHILDREN_LIMIT,
)
```

Yeni:
```python
from generators.base import (
    hex_to_rgb,
    parse_fills, parse_stroke, parse_corners, parse_effects, parse_layout,
    parse_text_style, parse_style_bundle,
    ColorValue, GradientDef, GradientStop, FillLayer, StrokeInfo, CornerRadii,
    ShadowEffect, BlurEffect, LayoutInfo, TextStyle, StyleBundle,
    SWIFTUI_WEIGHT_MAP, MAX_NATIVE_CHILDREN_LIMIT, MAX_DEPTH,
)
```

**Step 3: `figma_mcp.py`'deki import'u guncelle**

`figma_mcp.py`'de SwiftUI generator import'unu bul ve guncelle:

```python
# Eski
from swiftui_generator import generate_swiftui_code
# Yeni
from generators.swiftui_generator import generate_swiftui_code
```

**Step 4: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/swiftui_generator.py').read()); print('OK')"
```

**Step 5: Commit**

```bash
git add generators/swiftui_generator.py figma_mcp.py
git rm swiftui_generator.py  # eski dosyayi sil
git commit -m "refactor: move swiftui_generator to generators package, use base imports"
```

---

## Task 3: SwiftUI generator'a multi-fill + tum gradient turleri ekle

Mevcut `_swiftui_fill_modifier` (L:56-114) sadece ilk visible fill'de break ediyor ve ANGULAR gradient desteklemiyor. Multi-fill icin ZStack pattern'i kullanacagiz.

**Files:**
- Modify: `generators/swiftui_generator.py`

**Step 1: `_swiftui_fill_modifier` fonksiyonunu yeniden yaz**

Mevcut fonksiyonu (L:56-114) tamamen degistir:

```python
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
```

**Step 2: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add generators/swiftui_generator.py
git commit -m "feat: SwiftUI multi-fill + ANGULAR/DIAMOND gradient support"
```

---

## Task 4: SwiftUI gradient stroke + dashed border destegi

Mevcut `_swiftui_stroke_modifier` (L:142-170) sadece solid stroke destekliyor. Gradient stroke ve dashed border ekle.

**Files:**
- Modify: `generators/swiftui_generator.py`

**Step 1: `_swiftui_stroke_modifier` fonksiyonunu yeniden yaz**

```python
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
        r, g, b = c.rgb_ints
        color_code = f"Color(red: {r/255:.3f}, green: {g/255:.3f}, blue: {b/255:.3f})"
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
```

**Step 2: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add generators/swiftui_generator.py
git commit -m "feat: SwiftUI gradient stroke + dashed border support"
```

---

## Task 5: SwiftUI gradient text fill + typography iyilestirmeleri

Mevcut `_swiftui_text_node` (L:307-400) sadece solid text color destekliyor. Gradient text fill (`foregroundStyle`) ve eksik typography detaylarini ekle.

**Files:**
- Modify: `generators/swiftui_generator.py`

**Step 1: Text color rendering bolumunu guncelle**

`_swiftui_text_node` fonksiyonunda text color kismi (mevcut L:350-359 civari):

Eski yaklasim: Sadece solid fill'den renk cikarma
Yeni yaklasim: `parse_text_style()` kullan, gradient text destekle

```python
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
```

**Step 2: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/swiftui_generator.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add generators/swiftui_generator.py
git commit -m "feat: SwiftUI gradient text fill + enhanced typography"
```

---

## Task 6: SwiftUI blur + primary axis alignment iyilestirmeleri

Background blur ve primary axis alignment (SPACE_BETWEEN → Spacer()) eksik.

**Files:**
- Modify: `generators/swiftui_generator.py`

**Step 1: Blur effects guncelle**

`_swiftui_effects_modifier` fonksiyonunda (L:192-223 civari):

```python
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
```

**Step 2: Container node'a primary axis alignment ekle**

`_swiftui_container_node` fonksiyonunda layout mapping'e SPACE_BETWEEN desteği ekle. Children rendering sırasında, eğer `primaryAxisAlignItems == 'SPACE_BETWEEN'` ise, çocuklar arasına `Spacer()` ekle.

```python
# _swiftui_container_node icerisinde, children rendering bolumunde:
primary_align = node.get('primaryAxisAlignItems', 'MIN')

# Children rendering
for i, child in enumerate(children[:MAX_NATIVE_CHILDREN_LIMIT]):
    child_code = _generate_swiftui_node(child, indent + 4, depth + 1)
    if child_code:
        lines.append(child_code)
    # SPACE_BETWEEN: add Spacer between children
    if primary_align == 'SPACE_BETWEEN' and i < len(children) - 1:
        lines.append(f"{' ' * (indent + 4)}Spacer()")
```

**Step 3: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/swiftui_generator.py').read()); print('OK')"
```

**Step 4: Commit**

```bash
git add generators/swiftui_generator.py
git commit -m "feat: SwiftUI background blur + SPACE_BETWEEN alignment"
```

---

## Task 7: SwiftUI component naming iyilestirmesi

`generate_swiftui_code` fonksiyonunda component name "Iphone1314241" gibi anlamsiz isimler uretiyor. Figma frame isminden daha akilli isim uret.

**Files:**
- Modify: `generators/swiftui_generator.py`

**Step 1: Component name sanitizer ekle**

```python
import re

def _sanitize_component_name(name: str) -> str:
    """Convert Figma frame name to valid SwiftUI struct name.
    'iPhone 13 & 14 - 241' → 'Screen241'
    'Effects screen' → 'EffectsScreen'
    'Login Page' → 'LoginPage'
    """
    # Remove device names
    cleaned = re.sub(r'(?i)iphone\s*\d+\s*[&/,]*\s*\d*\s*[-–]\s*', '', name)
    cleaned = re.sub(r'(?i)ipad\s*\w*\s*[-–]\s*', '', cleaned)
    cleaned = re.sub(r'(?i)android\s*\w*\s*[-–]\s*', '', cleaned)
    cleaned = cleaned.strip(' -–')

    if not cleaned:
        cleaned = name  # Fallback to original

    # PascalCase conversion
    words = re.split(r'[\s_\-–/&]+', cleaned)
    pascal = ''.join(w.capitalize() for w in words if w)

    # Remove non-alphanumeric chars
    pascal = re.sub(r'[^a-zA-Z0-9]', '', pascal)

    # Ensure starts with letter
    if pascal and not pascal[0].isalpha():
        pascal = 'Screen' + pascal

    return pascal or 'GeneratedView'
```

**Step 2: `generate_swiftui_code`'da component_name fallback'i guncelle**

```python
# generate_swiftui_code fonksiyonunda:
if not component_name:
    component_name = _sanitize_component_name(node.get('name', 'GeneratedView'))
```

**Step 3: Commit**

```bash
git add generators/swiftui_generator.py
git commit -m "feat: intelligent SwiftUI component naming from Figma frame names"
```

---

## Task 8: React generator'i `generators/` altina tasi

React code generation fonksiyonlarini `figma_mcp.py`'den `generators/react_generator.py`'ye tasi.

**Files:**
- Create: `generators/react_generator.py`
- Modify: `figma_mcp.py` (fonksiyonlari kaldir, import ekle)

**Step 1: React fonksiyonlarini tasi**

`figma_mcp.py`'den su fonksiyonlari `generators/react_generator.py`'ye tasi:
- `_generate_react_code` (L:2806-2845)
- `_recursive_node_to_jsx` (L:3964-4359)

Bu fonksiyonlar icinde kullanilan helper'lar (`_get_background_css`, `_corner_radii_to_css`, `_transform_to_css`, `_blend_mode_to_css`, `_text_case_to_css`, `_text_decoration_to_css`, `_extract_stroke_data`, `_extract_effects_data`) simdilik `figma_mcp`'den import edilmeye devam etsin. Ileride bunlar da `base.py`'ye tasinabilir.

```python
# generators/react_generator.py
"""
React Code Generator - Recursive JSX rendering with Tailwind/CSS-in-JS support.
"""
from typing import Dict, Any, List
from figma_mcp import (
    _get_background_css, _corner_radii_to_css, _transform_to_css,
    _blend_mode_to_css, _text_case_to_css, _text_decoration_to_css,
    _extract_stroke_data, _extract_effects_data,
    TAILWIND_WEIGHT_MAP, TAILWIND_ALIGN_MAP, MAX_CHILDREN_LIMIT,
)

# ... tasanan fonksiyonlar ...
```

**Step 2: `figma_mcp.py`'de import'u guncelle**

```python
from generators.react_generator import generate_react_code
```

**Step 3: Syntax kontrolu**

```bash
python -c "import ast; ast.parse(open('generators/react_generator.py').read()); print('OK')"
```

**Step 4: Commit**

```bash
git add generators/react_generator.py figma_mcp.py
git commit -m "refactor: extract React generator to generators/react_generator.py"
```

---

## Task 9: Vue generator'i `generators/` altina tasi

**Files:**
- Create: `generators/vue_generator.py`
- Modify: `figma_mcp.py`

**Step 1: Vue fonksiyonlarini tasi**

`figma_mcp.py`'den tasanacak fonksiyonlar:
- `_generate_vue_code` (L:3061-3095)
- `_recursive_node_to_vue_template` (ilgili fonksiyon)
- `_generate_recursive_css` (L:3098-3190)

**Step 2: `figma_mcp.py`'de import'u guncelle**

```python
from generators.vue_generator import generate_vue_code
```

**Step 3: Commit**

```bash
git add generators/vue_generator.py figma_mcp.py
git commit -m "refactor: extract Vue generator to generators/vue_generator.py"
```

---

## Task 10: CSS/SCSS generator'lari `generators/` altina tasi

**Files:**
- Create: `generators/css_generator.py`
- Modify: `figma_mcp.py`

**Step 1: CSS fonksiyonlarini tasi**

`figma_mcp.py`'den tasanacak fonksiyonlar:
- `_generate_css_code` (L:3193-3350+)
- `_generate_scss_code` (L:3411+)
- `_recursive_node_to_css` ve ilgili fonksiyonlar

**Step 2: `figma_mcp.py`'de import'u guncelle**

```python
from generators.css_generator import generate_css_code, generate_scss_code
```

**Step 3: Commit**

```bash
git add generators/css_generator.py figma_mcp.py
git commit -m "refactor: extract CSS/SCSS generators to generators/css_generator.py"
```

---

## Task 11: Kotlin generator'i `generators/` altina tasi

**Files:**
- Create: `generators/kotlin_generator.py`
- Modify: `figma_mcp.py`

**Step 1: Kotlin fonksiyonlarini tasi**

`figma_mcp.py`'den tasanacak fonksiyonlar:
- `_generate_kotlin_code` (L:3635+)

**Step 2: `figma_mcp.py`'de import'u guncelle**

```python
from generators.kotlin_generator import generate_kotlin_code
```

**Step 3: Commit**

```bash
git add generators/kotlin_generator.py figma_mcp.py
git commit -m "refactor: extract Kotlin generator to generators/kotlin_generator.py"
```

---

## Task 12: `figma_mcp.py` temizligi

Tasanmis fonksiyonlari `figma_mcp.py`'den sil, dosya boyutunu kucult.

**Files:**
- Modify: `figma_mcp.py`

**Step 1: Tasanmis fonksiyonlari sil**

Su fonksiyonlar artik `generators/` altinda yasadigi icin `figma_mcp.py`'den silinebilir:
- `_generate_react_code` ve `_recursive_node_to_jsx`
- `_generate_vue_code` ve `_recursive_node_to_vue_template` ve `_generate_recursive_css`
- `_generate_css_code` ve `_generate_scss_code` ve `_recursive_node_to_css`
- `_generate_kotlin_code`

**NOT:** Helper fonksiyonlar (`_extract_fill_data`, `_get_background_css`, vs.) su asamada `figma_mcp.py`'de kalsin cunku `figma_get_node_details` ve diger MCP tool'lari hala bunlari kullaniyor. Bunlari ileri asamada `generators/base.py`'ye tasimak ayri bir refactoring plani.

**Step 2: Import'larin dogru calistigini dogrula**

```bash
python -c "from figma_mcp import mcp; print('Imports OK')"
```

**Step 3: Commit**

```bash
git add figma_mcp.py
git commit -m "refactor: remove migrated code generation functions from figma_mcp.py"
```

---

## Task 13: `implementationHints` framework-aware yapimi

`_generate_implementation_hints` (L:1486) her zaman CSS onerileri donuyor. Framework parametresi ekle.

**Files:**
- Modify: `figma_mcp.py` (`_generate_implementation_hints` fonksiyonu)

**Step 1: Framework parametresi ekle**

```python
def _generate_implementation_hints(node: Dict[str, Any], interactions: Optional[List] = None,
                                    framework: str = 'css') -> Dict[str, Any]:
    """Generate implementation hints aware of target framework."""
    hints = {}
    layout_mode = node.get('layoutMode')

    if framework in ('swiftui',):
        if layout_mode == 'VERTICAL':
            hints['layout'] = [f"Use VStack with spacing: {node.get('itemSpacing', 0)}"]
        elif layout_mode == 'HORIZONTAL':
            hints['layout'] = [f"Use HStack with spacing: {node.get('itemSpacing', 0)}"]
    elif framework in ('kotlin',):
        if layout_mode == 'VERTICAL':
            hints['layout'] = [f"Use Column with verticalArrangement spacedBy {node.get('itemSpacing', 0)}.dp"]
        elif layout_mode == 'HORIZONTAL':
            hints['layout'] = [f"Use Row with horizontalArrangement spacedBy {node.get('itemSpacing', 0)}.dp"]
    else:
        # Default CSS hints (existing behavior)
        if layout_mode == 'VERTICAL':
            hints['layout'] = [f"Use flexbox with flex-direction: column, gap: {node.get('itemSpacing', 0)}px"]
        elif layout_mode == 'HORIZONTAL':
            hints['layout'] = [f"Use flexbox with flex-direction: row, gap: {node.get('itemSpacing', 0)}px"]

    # ... rest of existing implementation hints logic ...
    return hints
```

**Step 2: Commit**

```bash
git add figma_mcp.py
git commit -m "feat: framework-aware implementation hints (SwiftUI, Kotlin, CSS)"
```

---

## Task 14: End-to-end dogrulama

Tum generator'larin dogru calistigini dogrula.

**Files:**
- None (sadece test)

**Step 1: Import dogrulamasi**

```bash
python -c "
from generators.base import parse_fills, parse_stroke, parse_corners, parse_effects, parse_layout, parse_text_style, parse_style_bundle
from generators.swiftui_generator import generate_swiftui_code
from generators.react_generator import generate_react_code
from generators.vue_generator import generate_vue_code
from generators.css_generator import generate_css_code, generate_scss_code
from generators.kotlin_generator import generate_kotlin_code
print('ALL IMPORTS OK')
"
```

**Step 2: MCP server baslatma dogrulamasi**

```bash
python -c "from figma_mcp import mcp; print('MCP server initialization OK')"
```

**Step 3: Version bump**

`pyproject.toml`'da version'u guncelle:
```
version = "3.0.0"
```

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 3.0.0 - modular generators + full property support"
```

---

## Ozet: Findings Doc Kapsamasi

| Bulgu # | Sorun | Cozum Task'i | Durum |
|---------|-------|-------------|-------|
| 1 | Recursive child traversal yok | Zaten var (swiftui_generator L:30-49) | Mevcut |
| 2 | Auto-layout mapping yok | Task 2 (base.py LayoutInfo) + mevcut | Mevcut + Gelistirilecek |
| 3 | Fill + opacity yok | Task 3 (multi-fill + tum gradientler) | YENi |
| 4 | Corner radius yok | Mevcut (swiftui_generator L:173-189) | Mevcut |
| 5 | Stroke rendering yok | Task 4 (gradient stroke + dashed) | YENI |
| 6 | Typography eksik | Task 5 (gradient text + enhanced) | YENI |
| 7 | Text renkleri eksik | Task 5 (parse_text_style) | YENI |
| 8 | Gradient fill yok (LINEAR) | Mevcut | Mevcut |
| 9 | RADIAL gradient yok | Mevcut | Mevcut |
| 10 | ANGULAR gradient yok | Task 3 (_gradient_to_swiftui) | YENI |
| 11 | Multi-fill katmanlari yok | Task 3 (ZStack pattern) | YENI |
| 12 | Gradient stroke yok | Task 4 | YENI |
| 13 | Gradient text fill yok | Task 5 (.foregroundStyle) | YENI |
| 14 | Blur hierarchy yok | Task 6 (background blur) | YENI |
| 15 | Horizontal scroll yok | Ileri asama (P1) | BEKLEMEDE |
| 16 | Dashed border yok | Task 4 | YENI |
| 17 | Component naming yanlis | Task 7 | YENI |
| 18 | implementationHints CSS | Task 13 | YENI |
| 19 | Image/asset referanslari yok | Task 3 (placeholder) | KISMI |
| 20 | Token truncation | Mevcut (onceki commit) | Mevcut |
