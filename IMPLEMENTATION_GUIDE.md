# Implementation Guide: Mobile Screen Pattern Detection

## 🎯 Goal
Fix SwiftUI code generation for mobile app screens by detecting Header+Content+TabBar pattern and adding ScrollView support.

---

## 📋 Changes Overview

### Files to Modify
1. `generators/base.py` - Add mobile pattern detection
2. `generators/swiftui_generator.py` - Integrate detection & generate mobile structure

---

## 🔧 STEP 1: Add Mobile Pattern Detection (base.py)

### Location: `generators/base.py` (after line 50)

```python
def detect_mobile_screen_pattern(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detect common mobile screen UI patterns.

    Pattern detection rules:
    1. Header: First child, small height (<120px), at top (<15% of screen)
    2. Content: Middle children, large height (>200px), fills most of screen
    3. Bottom bar: Last child, small height (<120px), at bottom (>85% of screen)

    Returns:
        Dict with pattern info if detected, None otherwise.
        {
            'is_mobile_screen': bool,
            'header': Optional[Dict],
            'content_children': List[Dict],
            'bottom_bar': Optional[Dict],
            'needs_scroll': bool,
            'available_height': float
        }
    """
    children = node.get('children', [])
    if len(children) < 2:
        return None

    # Get visible children with bounding boxes
    visible = [
        c for c in children
        if c.get('visible', True) and c.get('absoluteBoundingBox')
    ]
    if len(visible) < 2:
        return None

    # Sort by Y position
    sorted_children = sorted(
        visible,
        key=lambda c: c['absoluteBoundingBox'].get('y', 0)
    )

    container_bbox = node.get('absoluteBoundingBox', {})
    container_h = container_bbox.get('height', 0)
    if container_h == 0:
        return None

    # Check last child for bottom bar
    last = sorted_children[-1]
    last_bbox = last['absoluteBoundingBox']
    last_y = last_bbox.get('y', 0)
    last_h = last_bbox.get('height', 0)
    last_name = last.get('name', '').lower()

    has_bottom_bar = (
        last_h > 0 and last_h < 120 and  # Small height
        last_y > container_h * 0.85 and  # Near bottom
        (
            'navigation' in last_name or
            'tab' in last_name or
            'bar' in last_name or
            'bottom' in last_name or
            last.get('layoutMode') == 'HORIZONTAL'  # Tab bars usually horizontal
        )
    )

    # Check first child for header
    first = sorted_children[0]
    first_bbox = first['absoluteBoundingBox']
    first_h = first_bbox.get('height', 0)
    first_y = first_bbox.get('y', 0)
    first_name = first.get('name', '').lower()

    has_header = (
        first_h > 0 and first_h < 120 and  # Small height
        first_y < container_h * 0.15 and  # Near top
        (
            'header' in first_name or
            'nav' in first_name or
            'top' in first_name or
            first.get('layoutMode') == 'HORIZONTAL'  # Headers usually horizontal
        )
    )

    # Find content children (everything between header and bottom bar)
    start_idx = 1 if has_header else 0
    end_idx = len(sorted_children) - (1 if has_bottom_bar else 0)

    content_children = []
    for i in range(start_idx, end_idx):
        child = sorted_children[i]
        child_bbox = child['absoluteBoundingBox']
        child_h = child_bbox.get('height', 0)
        # Include children with significant height OR any child in middle section
        if child_h > 100 or (start_idx < i < end_idx):
            content_children.append(child)

    # Must have at least one content child
    if not content_children:
        return None

    # Calculate available height for content
    available_height = container_h
    if has_header:
        available_height -= first_h
    if has_bottom_bar:
        available_height -= last_h

    # Calculate total content height
    total_content_height = sum(
        c['absoluteBoundingBox'].get('height', 0)
        for c in content_children
    )

    # Add spacing between content children
    if len(content_children) > 1:
        # Estimate average gap (typical mobile UI: 8-24px)
        avg_gap = 16
        total_content_height += avg_gap * (len(content_children) - 1)

    # Needs scroll if content exceeds 95% of available space
    needs_scroll = total_content_height > available_height * 0.95

    # Pattern is valid if we have header OR bottom bar (at least one anchor point)
    is_valid_pattern = has_header or has_bottom_bar

    if not is_valid_pattern:
        return None

    return {
        'is_mobile_screen': True,
        'header': first if has_header else None,
        'content_children': content_children,
        'bottom_bar': last if has_bottom_bar else None,
        'needs_scroll': needs_scroll,
        'available_height': available_height,
        'total_content_height': total_content_height
    }
```

### Add to base.py exports (at end of file)
```python
# Export mobile pattern detection
__all__ = [
    # ... existing exports ...
    'detect_mobile_screen_pattern',
]
```

---

## 🔧 STEP 2: Update SwiftUI Generator (swiftui_generator.py)

### 2.1 Import mobile pattern detector

**Location:** Line 11 (after existing imports)

```python
from generators.base import (
    hex_to_rgb,
    parse_fills, parse_stroke, parse_corners, parse_effects, parse_layout,
    parse_text_style, parse_style_bundle,
    ColorValue, GradientDef, GradientStop, FillLayer, StrokeInfo, CornerRadii,
    ShadowEffect, BlurEffect, LayoutInfo, TextStyle, StyleBundle,
    SWIFTUI_WEIGHT_MAP, MAX_NATIVE_CHILDREN_LIMIT, MAX_DEPTH,
    sanitize_component_name, map_icon_name,
    detect_mobile_screen_pattern,  # ← ADD THIS
)
```

### 2.2 Update _analyze_children_layout

**Location:** Line 844, replace function with enhanced version

```python
def _analyze_children_layout(children: list, container_bbox: dict,
                             parent_node: Dict[str, Any] = None) -> tuple:
    """
    Analyze children positions to determine best container type.
    Now supports mobile screen pattern detection.

    Returns (container_type, estimated_spacing).
    container_type: 'VStack', 'HStack', 'VStack_Mobile', or 'ZStack'
    """
    visible = [c for c in children if c.get('visible', True) and c.get('absoluteBoundingBox')]
    if len(visible) <= 1:
        return 'ZStack', 0

    # NEW: Check for mobile screen pattern first
    mobile_pattern = None
    if parent_node:
        mobile_pattern = detect_mobile_screen_pattern(parent_node)

    # If this is a mobile screen with scroll needs, use VStack even with overlap
    if mobile_pattern and mobile_pattern['is_mobile_screen'] and mobile_pattern['needs_scroll']:
        return 'VStack_Mobile', 0  # Special marker for mobile screens

    # Sort by Y position
    sorted_by_y = sorted(visible, key=lambda c: c['absoluteBoundingBox'].get('y', 0))
    # Sort by X position
    sorted_by_x = sorted(visible, key=lambda c: c['absoluteBoundingBox'].get('x', 0))

    # MODIFIED: Increased overlap tolerance for mobile screens
    overlap_tolerance = 10 if mobile_pattern else 1  # Was always 1px

    # Check Y-axis sequential (no overlap within tolerance)
    y_sequential = True
    y_gaps = []
    for i in range(len(sorted_by_y) - 1):
        cur = sorted_by_y[i]['absoluteBoundingBox']
        nxt = sorted_by_y[i + 1]['absoluteBoundingBox']
        cur_bottom = cur.get('y', 0) + cur.get('height', 0)
        nxt_top = nxt.get('y', 0)
        if cur_bottom > nxt_top + overlap_tolerance:  # MODIFIED: use tolerance
            y_sequential = False
            break
        y_gaps.append(max(0, nxt_top - cur_bottom))

    if y_sequential and len(sorted_by_y) > 1:
        avg_gap = sum(y_gaps) / len(y_gaps) if y_gaps else 0
        return 'VStack', round(avg_gap)

    # Check X-axis sequential (no overlap within tolerance)
    x_sequential = True
    x_gaps = []
    for i in range(len(sorted_by_x) - 1):
        cur = sorted_by_x[i]['absoluteBoundingBox']
        nxt = sorted_by_x[i + 1]['absoluteBoundingBox']
        cur_right = cur.get('x', 0) + cur.get('width', 0)
        nxt_left = nxt.get('x', 0)
        if cur_right > nxt_left + overlap_tolerance:  # MODIFIED: use tolerance
            x_sequential = False
            break
        x_gaps.append(max(0, nxt_left - cur_right))

    if x_sequential and len(sorted_by_x) > 1:
        avg_gap = sum(x_gaps) / len(x_gaps) if x_gaps else 0
        return 'HStack', round(avg_gap)

    return 'ZStack', 0
```

### 2.3 Add mobile screen generator

**Location:** Line 1285 (after `_swiftui_empty_container` function)

```python
def _generate_mobile_screen_swiftui(node: Dict[str, Any], component_name: str,
                                     pattern: Dict[str, Any]) -> str:
    """
    Generate optimized SwiftUI structure for mobile screens.

    Structure:
        VStack(spacing: 0) {
            Header (if exists)
            ScrollView {
                VStack { Content children }
            }
            Bottom bar (if exists)
        }
    """
    header = pattern.get('header')
    content_children = pattern.get('content_children', [])
    bottom_bar = pattern.get('bottom_bar')
    needs_scroll = pattern.get('needs_scroll', False)

    lines = []

    # Generate header code
    header_code = None
    if header:
        header_code = _generate_swiftui_node(header, indent=12, depth=1, parent_node=node)

    # Generate content children
    content_lines = []
    for child in content_children:
        child_code = _generate_swiftui_node(child, indent=20 if needs_scroll else 16,
                                           depth=1, parent_node=node)
        if child_code:
            content_lines.append(child_code)

    content_code = '\n'.join(content_lines) if content_lines else '                    // No content'

    # Generate bottom bar code
    bottom_bar_code = None
    if bottom_bar:
        bottom_bar_code = _generate_swiftui_node(bottom_bar, indent=12, depth=1, parent_node=node)

    # Get root modifiers (background, etc.)
    root_modifiers, gradient_def = _swiftui_collect_modifiers(node, include_frame=False)

    # Build structure
    if needs_scroll:
        # With ScrollView
        scroll_content = f"""VStack(spacing: 0) {{"""

        if header_code:
            scroll_content += f"\n{header_code}"

        scroll_content += f"""
            ScrollView {{
                VStack(alignment: .leading, spacing: 16) {{
{content_code}
                }}
                .padding(.horizontal, 16)
            }}"""

        if bottom_bar_code:
            scroll_content += f"\n{bottom_bar_code}"

        scroll_content += "\n        }"
    else:
        # No scroll needed
        scroll_content = f"""VStack(spacing: 0) {{"""

        if header_code:
            scroll_content += f"\n{header_code}"

        scroll_content += f"""
            VStack(alignment: .leading, spacing: 16) {{
{content_code}
            }}
            .padding(.horizontal, 16)"""

        if bottom_bar_code:
            scroll_content += f"\n{bottom_bar_code}"

        scroll_content += "\n        }"

    # Apply root modifiers
    modifiers_str = '\n        '.join(root_modifiers) if root_modifiers else ''

    # Get frame size (width only, height flexible for scrolling)
    bbox = node.get('absoluteBoundingBox', {})
    w = int(bbox.get('width', 390))
    frame_modifier = f".frame(width: {w})"

    # Build complete code
    gradient_section = f'\n{gradient_def}\n' if gradient_def else ''

    code = f'''import SwiftUI

struct {component_name}: View {{{gradient_section}
    var body: some View {{
        {scroll_content}
        {frame_modifier}
        {modifiers_str}
    }}
}}

#Preview {{
    {component_name}()
}}'''

    # Add RoundedCorner helper if needed
    if 'RoundedCorner' in code:
        code += _rounded_corner_shape()

    return code
```

### 2.4 Update generate_swiftui_code entry point

**Location:** Line 1298, replace function with enhanced version

```python
def generate_swiftui_code(node: Dict[str, Any], component_name: str = '') -> str:
    """
    Generate complete SwiftUI view from Figma node tree.

    NEW: Detects mobile screen patterns and generates optimized structure.

    Public entry point. Produces a full SwiftUI struct with:
    - Import statement
    - View struct with body
    - Gradient definitions if needed
    - Preview provider
    - RoundedCorner helper shape if needed
    """
    if not component_name:
        component_name = _sanitize_component_name(node.get('name', 'GeneratedView'))

    # NEW: Detect mobile screen pattern
    mobile_pattern = detect_mobile_screen_pattern(node)

    if mobile_pattern and mobile_pattern['is_mobile_screen']:
        # Use specialized mobile screen generator
        return _generate_mobile_screen_swiftui(node, component_name, mobile_pattern)

    # EXISTING CODE: Regular container generation
    # (rest of the function remains unchanged)

    # Generate body content
    body_code = _generate_swiftui_node(node, indent=12, depth=0)
    if not body_code:
        body_code = '            // Empty content'

    # ... rest of existing code ...
```

---

## 🧪 STEP 3: Testing

### Test Case 1: Node 144-3313

**Before:**
```swift
ZStack() {
    VStack(...).offset(x: 0, y: 571)   // Tab bar
    HStack(...).offset(x: 0, y: -534)  // Header
    VStack(...).offset(x: 0, y: 26)    // Content (no scroll!)
}
```

**Expected After:**
```swift
VStack(spacing: 0) {
    HStack(...) { /* Header */ }
    ScrollView {
        VStack(...) { /* Content */ }
    }
    VStack(...) { /* Tab bar */ }
}
```

### Test Script

```python
# test_mobile_pattern.py
import json
from generators.base import detect_mobile_screen_pattern
from generators.swiftui_generator import generate_swiftui_code

# Load test node data
with open('test_data/node_144_3313.json') as f:
    node = json.load(f)

# Test detection
pattern = detect_mobile_screen_pattern(node)
print("Mobile Pattern Detected:")
print(json.dumps(pattern, indent=2))

# Test code generation
code = generate_swiftui_code(node, "TestScreen")
print("\nGenerated Code:")
print(code)

# Assertions
assert pattern is not None
assert pattern['is_mobile_screen'] == True
assert pattern['needs_scroll'] == True
assert pattern['header'] is not None
assert pattern['bottom_bar'] is not None
assert len(pattern['content_children']) > 0
assert 'ScrollView' in code
assert 'ZStack' not in code or code.count('ZStack') < 3  # Only for icons
print("\n✅ All tests passed!")
```

### Manual Testing

1. Generate code for node 144-3313
2. Copy to Xcode
3. Verify:
   - ✅ Compiles without errors
   - ✅ ScrollView present
   - ✅ Content scrolls smoothly
   - ✅ Header stays at top
   - ✅ Tab bar stays at bottom
   - ✅ No absolute positioning (.offset only for icons)

---

## 📊 STEP 4: Validation

### Success Criteria

- [ ] `detect_mobile_screen_pattern()` correctly identifies mobile screens
- [ ] Overlap tolerance increased to 10px for mobile screens
- [ ] ScrollView added when content exceeds available height
- [ ] VStack structure used instead of ZStack
- [ ] Generated code compiles in Xcode
- [ ] UI looks identical to Figma design
- [ ] Scroll behavior works correctly

### Performance

- Pattern detection adds ~5ms per node (negligible)
- Code generation time: same as before
- Generated code performance: better (native SwiftUI layout vs absolute positioning)

---

## 🐛 Edge Cases

### Case 1: No Header, Only Bottom Bar
```python
# Pattern should still be detected
pattern = {
    'header': None,
    'content_children': [...],
    'bottom_bar': {...},
    'needs_scroll': True
}
```

### Case 2: Header + Content, No Bottom Bar
```python
# Pattern should still be detected
pattern = {
    'header': {...},
    'content_children': [...],
    'bottom_bar': None,
    'needs_scroll': True
}
```

### Case 3: Content Fits Without Scroll
```python
# ScrollView should NOT be added
pattern = {
    'header': {...},
    'content_children': [...],
    'bottom_bar': {...},
    'needs_scroll': False  # ← Don't add ScrollView
}
```

### Case 4: False Positive (Not Mobile Screen)
```python
# Pattern should be None
pattern = None  # Continue with regular ZStack/VStack logic
```

---

## 📝 Checklist

### Implementation
- [ ] Add `detect_mobile_screen_pattern()` to base.py
- [ ] Update imports in swiftui_generator.py
- [ ] Modify `_analyze_children_layout()` with tolerance
- [ ] Add `_generate_mobile_screen_swiftui()` function
- [ ] Update `generate_swiftui_code()` entry point

### Testing
- [ ] Unit test for pattern detection
- [ ] Integration test for node 144-3313
- [ ] Test with other mobile screens (onboarding, profile)
- [ ] Test edge cases (no header, no bottom bar, etc.)
- [ ] Compile generated code in Xcode

### Documentation
- [ ] Update CHANGELOG.md
- [ ] Add docstrings to new functions
- [ ] Update README with mobile pattern support

---

## 🚀 Deployment

### Version Bump
- Current: v3.2.13
- Next: v3.3.0 (minor version - new feature)

### Changelog Entry
```markdown
### v3.3.0 - Mobile Screen Pattern Detection

**New Features:**
- Automatic detection of mobile screen patterns (Header + Content + TabBar)
- Intelligent ScrollView injection for vertical overflow
- Increased overlap tolerance for mobile UI layouts (10px vs 1px)

**Improvements:**
- Generated code now uses VStack + ScrollView instead of ZStack + offsets
- Better maintainability and responsive behavior
- SwiftUI best practices compliance

**Bug Fixes:**
- Fixed false positive overlaps in mobile screens causing ZStack usage
- Content no longer truncated in tall mobile screens
```

---

## ⏱️ Time Estimate

- **Implementation:** 2-3 hours
- **Testing:** 1-2 hours
- **Documentation:** 30 min
- **Total:** 4-6 hours

---

**Ready to implement!** Start with Step 1 (base.py) and test incrementally.
