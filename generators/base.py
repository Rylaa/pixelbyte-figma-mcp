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
import re


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CHILDREN_LIMIT = 20       # React/Vue/CSS child limit per container
MAX_NATIVE_CHILDREN_LIMIT = 15  # SwiftUI/Kotlin child limit
MAX_DEPTH = 12                  # Max recursive depth

# Common Figma icon name patterns → SF Symbols mapping
ICON_NAME_MAP = {
    # Solar icons
    'settings': 'gearshape', 'setting': 'gearshape', 'gear': 'gearshape',
    'search': 'magnifyingglass', 'find': 'magnifyingglass',
    'home': 'house', 'house': 'house',
    'user': 'person', 'person': 'person', 'profile': 'person',
    'heart': 'heart.fill', 'like': 'heart.fill', 'favorite': 'heart.fill',
    'star': 'star.fill', 'rating': 'star.fill',
    'bell': 'bell', 'notification': 'bell', 'alarm': 'bell',
    'mail': 'envelope', 'email': 'envelope', 'message': 'envelope',
    'chat': 'bubble.left', 'comment': 'bubble.left', 'comment-dots': 'bubble.left',
    'thumbs-up': 'hand.thumbsup', 'thumbsup': 'hand.thumbsup', 'thumb-up': 'hand.thumbsup',
    'anchor': 'anchor',
    'share': 'square.and.arrow.up', 'export': 'square.and.arrow.up',
    'download': 'arrow.down.circle', 'import': 'arrow.down.circle',
    'upload': 'arrow.up.circle',
    'close': 'xmark', 'x': 'xmark', 'cancel': 'xmark', 'remove': 'xmark',
    'add': 'plus', 'plus': 'plus', 'create': 'plus',
    'minus': 'minus', 'subtract': 'minus',
    'check': 'checkmark', 'done': 'checkmark', 'tick': 'checkmark',
    'arrow-left': 'arrow.left', 'back': 'chevron.left', 'chevron-left': 'chevron.left',
    'arrow-right': 'arrow.right', 'forward': 'chevron.right', 'chevron-right': 'chevron.right',
    'arrow-up': 'arrow.up', 'chevron-up': 'chevron.up',
    'arrow-down': 'arrow.down', 'chevron-down': 'chevron.down',
    'eye': 'eye', 'view': 'eye', 'visible': 'eye', 'show': 'eye',
    'eye-off': 'eye.slash', 'hide': 'eye.slash', 'invisible': 'eye.slash',
    'lock': 'lock', 'locked': 'lock', 'secure': 'lock',
    'unlock': 'lock.open',
    'trash': 'trash', 'delete': 'trash', 'bin': 'trash',
    'edit': 'pencil', 'pencil': 'pencil', 'write': 'pencil',
    'copy': 'doc.on.doc', 'duplicate': 'doc.on.doc',
    'camera': 'camera', 'photo': 'photo',
    'image': 'photo', 'picture': 'photo', 'gallery': 'photo',
    'video': 'video', 'film': 'video', 'movie': 'video',
    'play': 'play.fill', 'start': 'play.fill',
    'pause': 'pause.fill', 'stop': 'stop.fill',
    'music': 'music.note', 'audio': 'music.note',
    'mic': 'mic', 'microphone': 'mic',
    'phone': 'phone', 'call': 'phone',
    'location': 'location', 'map': 'map', 'pin': 'mappin',
    'calendar': 'calendar', 'date': 'calendar', 'schedule': 'calendar',
    'clock': 'clock', 'time': 'clock', 'timer': 'timer',
    'wifi': 'wifi', 'signal': 'wifi',
    'bluetooth': 'wave.3.right',
    'battery': 'battery.100',
    'sun': 'sun.max', 'light': 'sun.max', 'brightness': 'sun.max',
    'moon': 'moon', 'dark': 'moon', 'night': 'moon',
    'cloud': 'cloud', 'weather': 'cloud',
    'folder': 'folder', 'directory': 'folder',
    'file': 'doc', 'document': 'doc',
    'link': 'link', 'url': 'link', 'chain': 'link',
    'globe': 'globe', 'web': 'globe', 'world': 'globe', 'internet': 'globe',
    'filter': 'line.3.horizontal.decrease', 'sort': 'arrow.up.arrow.down',
    'menu': 'line.3.horizontal', 'hamburger': 'line.3.horizontal',
    'more': 'ellipsis', 'dots': 'ellipsis', 'options': 'ellipsis',
    'info': 'info.circle', 'about': 'info.circle',
    'help': 'questionmark.circle', 'question': 'questionmark.circle',
    'warning': 'exclamationmark.triangle', 'alert': 'exclamationmark.triangle',
    'exclamation': 'exclamationmark.triangle.fill',
    'error': 'xmark.circle', 'danger': 'xmark.circle',
    'success': 'checkmark.circle', 'verified': 'checkmark.circle',
    'refresh': 'arrow.clockwise', 'reload': 'arrow.clockwise', 'sync': 'arrow.clockwise',
    'send': 'paperplane', 'submit': 'paperplane',
    'attach': 'paperclip', 'attachment': 'paperclip',
    'bookmark': 'bookmark', 'save': 'bookmark',
    'tag': 'tag', 'label': 'tag',
    'cart': 'cart', 'shopping': 'cart', 'bag': 'bag',
    'credit-card': 'creditcard', 'payment': 'creditcard',
    'dollar': 'dollarsign.circle', 'money': 'dollarsign.circle',
    'chart': 'chart.bar', 'analytics': 'chart.bar', 'graph': 'chart.bar',
    'trending': 'chart.line.uptrend.xyaxis',
    'fire': 'flame', 'hot': 'flame',
    'bolt': 'bolt', 'lightning': 'bolt', 'flash': 'bolt', 'zap': 'bolt.fill',
    'shield': 'shield', 'security': 'shield',
    'key': 'key',
    'focus': 'viewfinder', 'focus-mode': 'viewfinder', 'scope': 'viewfinder',
    'goal': 'scope', 'target': 'scope', 'aim': 'scope', 'bullseye': 'scope',
    'sparkle': 'sparkles', 'sparkles': 'sparkles', 'stars': 'sparkles', 'magic': 'sparkles', 'ai': 'sparkles', 'wand': 'wand.and.stars',
    'button': 'rectangle.on.rectangle', 'button-solid': 'rectangle.on.rectangle',
    'logout': 'rectangle.portrait.and.arrow.right', 'signout': 'rectangle.portrait.and.arrow.right',
    'login': 'rectangle.portrait.and.arrow.forward', 'signin': 'rectangle.portrait.and.arrow.forward',
}


def sanitize_component_name(name: str) -> str:
    """Convert Figma frame name to valid component name.

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


def map_icon_name(figma_name: str) -> str:
    """Map Figma icon name to SF Symbols name.

    'solar:settings-linear' -> 'gearshape'
    'mdi:heart' -> 'heart.fill'
    'lucide/clock' -> 'clock'
    'eye' -> 'eye'
    """
    # Strip icon library prefix (e.g., "solar:", "mdi:", "lucide:", "lucide/")
    clean = figma_name
    if ':' in clean:
        clean = clean.split(':')[-1]
    elif '/' in clean:
        clean = clean.split('/')[-1]
    # Remove common suffixes (style variants and size)
    clean = re.sub(r'[-_](linear|outline|filled|bold|solid|regular|light|thin|duotone|broken)$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[-_]\d+$', '', clean)  # Remove size suffixes like -16, -24, -32
    clean = clean.lower().strip().replace('_', '-').replace(' ', '-')

    # Direct match
    if clean in ICON_NAME_MAP:
        return ICON_NAME_MAP[clean]

    # Partial match - check if any key is contained in the name
    # Require min 3 chars to avoid single-char false positives (e.g., 'x' in 'text')
    # Sort by key length descending for longest match first
    for key, symbol in sorted(ICON_NAME_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if len(key) >= 3 and key in clean:
            return symbol

    return 'square.dashed'  # Fallback: recognizable placeholder


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
            ai = int(self.a * 255)
            return f"#{ri:02x}{gi:02x}{bi:02x}{ai:02x}"
        return f"#{ri:02x}{gi:02x}{bi:02x}"

    @property
    def rgba(self) -> str:
        ri, gi, bi = int(self.r * 255), int(self.g * 255), int(self.b * 255)
        if self.a < 1:
            return f"rgba({ri}, {gi}, {bi}, {self.a:.2f})"
        return f"rgb({ri}, {gi}, {bi})"

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
    stroke_item_dashes = []
    for s in strokes:
        if not s.get('visible', True):
            continue
        s_type = s.get('type', '')
        layer = FillLayer(type=s_type, visible=True, opacity=s.get('opacity', 1.0))
        # Collect dashes from individual stroke items as fallback
        item_dashes = s.get('strokeDashes', []) or s.get('dashPattern', []) or s.get('dashes', [])
        if item_dashes and not stroke_item_dashes:
            stroke_item_dashes = item_dashes
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

    dashes = node.get('strokeDashes', []) or node.get('dashPattern', []) or stroke_item_dashes
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


# ---------------------------------------------------------------------------
# CSS-oriented helpers (shared by React, Vue, CSS generators)
# ---------------------------------------------------------------------------
# These were originally in figma_mcp.py and are duplicated here to break
# circular imports.  The figma_mcp copies remain for its own internal use.

import re as _re


def _rgb_to_hsl(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """Convert RGB (0-255) to HSL (h: 0-360, s: 0-100, l: 0-100)."""
    r2, g2, b2 = r / 255, g / 255, b / 255
    max_c, min_c = max(r2, g2, b2), min(r2, g2, b2)
    l = (max_c + min_c) / 2

    if max_c == min_c:
        h = s = 0.0
    else:
        d = max_c - min_c
        s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
        if max_c == r2:
            h = (g2 - b2) / d + (6 if g2 < b2 else 0)
        elif max_c == g2:
            h = (b2 - r2) / d + 2
        else:
            h = (r2 - g2) / d + 4
        h /= 6

    return (round(h * 360), round(s * 100), round(l * 100))


def _calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance for WCAG contrast ratio (0-255 RGB values)."""
    def adjust(c: int) -> float:
        c2 = c / 255
        return c2 / 12.92 if c2 <= 0.03928 else ((c2 + 0.055) / 1.055) ** 2.4
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def _contrast_ratio(color1_rgb: tuple, color2_rgb: tuple) -> float:
    """Calculate WCAG contrast ratio between two colors (RGB tuples 0-255)."""
    l1 = _calculate_luminance(*color1_rgb)
    l2 = _calculate_luminance(*color2_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def _calculate_gradient_angle(handle_positions: List[Dict[str, float]]) -> float:
    """Calculate gradient angle from Figma handle positions."""
    if not handle_positions or len(handle_positions) < 2:
        return 0
    start = handle_positions[0]
    end = handle_positions[1]
    dx = end.get('x', 0) - start.get('x', 0)
    dy = end.get('y', 0) - start.get('y', 0)
    angle = math.degrees(math.atan2(dy, dx))
    css_angle = 90 - angle
    return round(css_angle, 2)


# Underscore-prefixed aliases matching the names used by generators
def _rgba_to_hex(color: Dict[str, float]) -> str:
    """Convert Figma RGBA color to hex."""
    return rgba_to_hex(color)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple (0-255)."""
    return hex_to_rgb(hex_color)


def _extract_gradient_stops(gradient_stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract gradient color stops."""
    stops = []
    for stop in gradient_stops:
        color = stop.get('color', {})
        stops.append({
            'position': round(stop.get('position', 0), 4),
            'color': rgba_to_hex(color),
            'opacity': color.get('a', 1)
        })
    return stops


def _extract_stroke_data(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract comprehensive stroke data."""
    strokes = node.get('strokes', [])
    if not strokes:
        return None

    stroke_colors = []
    for stroke in strokes:
        if stroke.get('visible', True):
            stroke_type = stroke.get('type', 'SOLID')
            stroke_data: Dict[str, Any] = {
                'type': stroke_type,
                'opacity': stroke.get('opacity', 1),
                'blendMode': stroke.get('blendMode', 'NORMAL')
            }
            if stroke_type == 'SOLID':
                hex_color = rgba_to_hex(stroke.get('color', {}))
                stroke_data['hex'] = hex_color
                stroke_data['color'] = hex_color
                rgb = hex_to_rgb(hex_color)
                hsl = _rgb_to_hsl(*rgb)
                stroke_data['rgb'] = f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
                stroke_data['hsl'] = f"{hsl[0]}, {hsl[1]}%, {hsl[2]}%"
                stroke_data['contrast'] = {
                    'white': _contrast_ratio(rgb, (255, 255, 255)),
                    'black': _contrast_ratio(rgb, (0, 0, 0))
                }
            elif stroke_type.startswith('GRADIENT_'):
                stroke_data['gradient'] = {
                    'type': stroke_type.replace('GRADIENT_', ''),
                    'stops': _extract_gradient_stops(stroke.get('gradientStops', [])),
                    'handlePositions': stroke.get('gradientHandlePositions', [])
                }
            stroke_colors.append(stroke_data)

    individual_weights: Dict[str, Any] = {}
    for side, key in [('top', 'strokeTopWeight'), ('right', 'strokeRightWeight'),
                       ('bottom', 'strokeBottomWeight'), ('left', 'strokeLeftWeight')]:
        if key in node:
            individual_weights[side] = node[key]

    result: Dict[str, Any] = {
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


def _extract_effects_data(node: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all effects (shadows, blurs) from a node."""
    effects = node.get('effects', [])
    shadows = []
    blurs = []

    for effect in effects:
        if not effect.get('visible', True):
            continue
        effect_type = effect.get('type', '')
        if effect_type in ['DROP_SHADOW', 'INNER_SHADOW']:
            color = effect.get('color', {})
            offset = effect.get('offset', {'x': 0, 'y': 0})
            hex_color = rgba_to_hex(color)
            rgb = hex_to_rgb(hex_color)
            hsl = _rgb_to_hsl(*rgb)
            shadows.append({
                'type': effect_type,
                'hex': hex_color,
                'color': hex_color,
                'rgb': f"{rgb[0]}, {rgb[1]}, {rgb[2]}",
                'hsl': f"{hsl[0]}, {hsl[1]}%, {hsl[2]}%",
                'contrast': {
                    'white': _contrast_ratio(rgb, (255, 255, 255)),
                    'black': _contrast_ratio(rgb, (0, 0, 0))
                },
                'offset': {
                    'x': offset.get('x', 0),
                    'y': offset.get('y', 0)
                },
                'radius': effect.get('radius', 0),
                'spread': effect.get('spread', 0),
                'blendMode': effect.get('blendMode', 'NORMAL'),
                'showShadowBehindNode': effect.get('showShadowBehindNode', False)
            })
        elif effect_type in ['LAYER_BLUR', 'BACKGROUND_BLUR']:
            blurs.append({
                'type': effect_type,
                'radius': effect.get('radius', 0)
            })

    return {
        'shadows': shadows if shadows else None,
        'blurs': blurs if blurs else None
    }


def _gradient_to_css(fill: Dict[str, Any]) -> Optional[str]:
    """Convert Figma gradient fill to CSS gradient string."""
    fill_type = fill.get('type', '')
    if 'GRADIENT' not in fill_type:
        return None
    gradient_stops = fill.get('gradientStops', [])
    if not gradient_stops:
        return None
    stops_css = []
    for stop in gradient_stops:
        color = stop.get('color', {})
        position = stop.get('position', 0)
        hex_color = rgba_to_hex(color)
        alpha = color.get('a', 1)
        if alpha < 1:
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            stops_css.append(f"rgba({r}, {g}, {b}, {alpha:.2f}) {int(position * 100)}%")
        else:
            stops_css.append(f"{hex_color} {int(position * 100)}%")
    stops_str = ', '.join(stops_css)
    if fill_type == 'GRADIENT_LINEAR':
        handle_positions = fill.get('gradientHandlePositions', [])
        angle = _calculate_gradient_angle(handle_positions)
        return f"linear-gradient({int(angle)}deg, {stops_str})"
    elif fill_type == 'GRADIENT_RADIAL':
        return f"radial-gradient(circle, {stops_str})"
    elif fill_type == 'GRADIENT_ANGULAR':
        return f"conic-gradient({stops_str})"
    elif fill_type == 'GRADIENT_DIAMOND':
        return f"radial-gradient(ellipse, {stops_str})"
    return None


def _get_single_fill_css(fill: Dict[str, Any]) -> Optional[str]:
    """Convert a single fill to CSS value."""
    if not fill.get('visible', True):
        return None
    fill_type = fill.get('type', '')
    if fill_type == 'SOLID':
        color = fill.get('color', {})
        opacity = fill.get('opacity', 1)
        hex_color = rgba_to_hex(color)
        if opacity < 1:
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            return f"rgba({r}, {g}, {b}, {opacity:.2f})"
        return hex_color
    elif 'GRADIENT' in fill_type:
        gradient_css = _gradient_to_css(fill)
        if gradient_css:
            return gradient_css
    elif fill_type == 'IMAGE':
        image_ref = fill.get('imageRef', '')
        scale_mode = fill.get('scaleMode', 'FILL')
        if scale_mode == 'FILL':
            return f"url(/* imageRef: {image_ref} */) center/cover no-repeat"
        elif scale_mode == 'FIT':
            return f"url(/* imageRef: {image_ref} */) center/contain no-repeat"
        elif scale_mode == 'TILE':
            return f"url(/* imageRef: {image_ref} */) repeat"
        else:
            return f"url(/* imageRef: {image_ref} */)"
    return None


def _get_background_css(node: Dict[str, Any]) -> tuple:
    """Extract background CSS (color or gradient) from node fills.

    Returns:
        tuple: (background_value, background_type)
    """
    fills = node.get('fills', [])
    if not fills:
        return None, None
    css_values = []
    fill_types = []
    for fill in fills:
        css_value = _get_single_fill_css(fill)
        if css_value:
            css_values.append(css_value)
            ft = fill.get('type', 'SOLID')
            if 'GRADIENT' in ft:
                fill_types.append('gradient')
            elif ft == 'IMAGE':
                fill_types.append('image')
            else:
                fill_types.append('color')
    if not css_values:
        return None, None
    if len(css_values) == 1:
        return css_values[0], fill_types[0]
    css_values.reverse()
    fill_types.reverse()
    return ', '.join(css_values), 'layered'


def _corner_radii_to_css(node: Dict[str, Any]) -> str:
    """Convert Figma corner radii to CSS border-radius."""
    if 'rectangleCornerRadii' in node:
        radii = node['rectangleCornerRadii']
        if len(radii) == 4:
            tl, tr, br, bl = radii
            if tl == tr == br == bl:
                return f"{int(tl)}px"
            return f"{int(tl)}px {int(tr)}px {int(br)}px {int(bl)}px"
    corner_radius = node.get('cornerRadius', 0)
    if corner_radius:
        return f"{int(corner_radius)}px"
    return ""


def _transform_to_css(node: Dict[str, Any]) -> Optional[str]:
    """Convert Figma transform properties to CSS transform."""
    transforms = []
    rotation = node.get('rotation', 0)
    if rotation:
        angle_deg = -math.degrees(rotation)
        if abs(angle_deg) > 0.1:
            transforms.append(f"rotate({angle_deg:.1f}deg)")
    relative_transform = node.get('relativeTransform')
    if relative_transform and len(relative_transform) >= 2:
        a = relative_transform[0][0] if len(relative_transform[0]) > 0 else 1
        b = relative_transform[0][1] if len(relative_transform[0]) > 1 else 0
        c = relative_transform[1][0] if len(relative_transform[1]) > 0 else 0
        d = relative_transform[1][1] if len(relative_transform[1]) > 1 else 1
        # Detect horizontal/vertical flip (negative scale values)
        if a < -0.01:
            transforms.append("scaleX(-1)")
        if d < -0.01:
            transforms.append("scaleY(-1)")
        # Check for non-unit scale (magnitude, since flip handled above)
        scale_x = (a**2 + c**2)**0.5
        scale_y = (b**2 + d**2)**0.5
        if abs(scale_x - 1) > 0.01 or abs(scale_y - 1) > 0.01:
            if abs(scale_x - scale_y) < 0.01:
                transforms.append(f"scale({scale_x:.2f})")
            else:
                transforms.append(f"scale({scale_x:.2f}, {scale_y:.2f})")
    return ' '.join(transforms) if transforms else None


def _blend_mode_to_css(blend_mode: str) -> Optional[str]:
    """Convert Figma blend mode to CSS mix-blend-mode."""
    blend_map = {
        'PASS_THROUGH': None, 'NORMAL': None,
        'DARKEN': 'darken', 'MULTIPLY': 'multiply',
        'LINEAR_BURN': 'color-burn', 'COLOR_BURN': 'color-burn',
        'LIGHTEN': 'lighten', 'SCREEN': 'screen',
        'LINEAR_DODGE': 'color-dodge', 'COLOR_DODGE': 'color-dodge',
        'OVERLAY': 'overlay', 'SOFT_LIGHT': 'soft-light',
        'HARD_LIGHT': 'hard-light', 'DIFFERENCE': 'difference',
        'EXCLUSION': 'exclusion', 'HUE': 'hue',
        'SATURATION': 'saturation', 'COLOR': 'color',
        'LUMINOSITY': 'luminosity'
    }
    return blend_map.get(blend_mode)


def _text_case_to_css(text_case: str) -> Optional[str]:
    """Convert Figma textCase to CSS text-transform."""
    case_map = {
        'ORIGINAL': None, 'UPPER': 'uppercase',
        'LOWER': 'lowercase', 'TITLE': 'capitalize',
        'SMALL_CAPS': None, 'SMALL_CAPS_FORCED': None
    }
    return case_map.get(text_case)


def _text_decoration_to_css(decoration: str) -> Optional[str]:
    """Convert Figma textDecoration to CSS text-decoration."""
    decoration_map = {
        'NONE': None, 'UNDERLINE': 'underline',
        'STRIKETHROUGH': 'line-through'
    }
    return decoration_map.get(decoration)


def _sanitize_token_name(name: str) -> str:
    """Sanitize token name for use in CSS/SCSS variables and Tailwind config."""
    sanitized = _re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
    sanitized = sanitized.strip('-')
    return sanitized or 'unnamed'
