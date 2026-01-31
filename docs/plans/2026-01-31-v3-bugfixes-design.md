# v3.0.0 Bugfix & Improvement Plan

**Date:** 2026-01-31
**Status:** Approved

## Issues to Address

### 1. P0 - CornerRadii Crash (generate_code broken)
**Error:** `AttributeError: 'CornerRadii' object has no attribute 'get'`
**Root Cause:** `parse_corners()` returns `CornerRadii` dataclass but SwiftUI generator treats it as dict.

**Fix locations:**
- `generators/swiftui_generator.py:238-248` - `_swiftui_corner_modifier()`
- `generators/swiftui_generator.py:469-470` - `_swiftui_shape_node()`
- `generators/swiftui_generator.py:531-536` - container corner handling
- `figma_mcp.py:2021-2025` - `_build_css_ready_border()`
- Check `generators/kotlin_generator.py` for same pattern

**Approach:** Convert all dict-style access to dataclass property access:
- `corner_radii.get('isUniform')` → `corner_radii.is_uniform`
- `corner_radii['topLeft']` → `corner_radii.top_left`
- `corner_radii.get('topLeft', 0)` → `corner_radii.top_left`

### 2. implementationHints Framework Parameter
**Problem:** `_generate_implementation_hints()` is framework-aware but called without framework param.
**Fix:** Add optional `framework` field to `FigmaNodeInput` model, pass it through to `_generate_implementation_hints()`.

### 3. Recursive Child Traversal (Depth-2)
**Problem:** `get_node_details` only shows `childrenCount`, no child details.
**Fix:** Add depth-2 recursive child detail extraction to `get_node_details()`:
- Direct children: name, type, size, fills summary, text content
- Grandchildren: name, type, size (lighter)
- Respect existing depth/count limits to prevent response bloat

### 4. Token Truncation Limit Increase
**Problem:** 30 items/category too restrictive (truncates typography at 26+, spacing at 75+).
**Fix:** Increase `max_per_category` from 30 to 100 in Stage 2 truncation (figma_mcp.py:3761-3772).

## Implementation Order
1. P0 CornerRadii fix (unblocks all code generation)
2. Token truncation limit (one-line change)
3. implementationHints framework param
4. Child traversal depth-2
