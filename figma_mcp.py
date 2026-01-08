#!/usr/bin/env python3
"""
Figma MCP Server - Model Context Protocol server for Figma API integration.

This server provides tools to interact with Figma REST API, including:
- File structure retrieval
- Node details and styles
- Screenshot/image export
- Design token extraction (colors, fonts, spacing)
- Code generation (React, Vue, Tailwind CSS)

Author: Yusuf Demirkoparan
"""

import os
import json
import re
import base64
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# ============================================================================
# Constants
# ============================================================================

FIGMA_API_BASE = "https://api.figma.com/v1"
CHARACTER_LIMIT = 25000
DEFAULT_TIMEOUT = 30.0

# ============================================================================
# Initialize MCP Server
# ============================================================================

mcp = FastMCP("figma_mcp")

# ============================================================================
# Enums and Types
# ============================================================================

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class ImageFormat(str, Enum):
    """Image export format."""
    PNG = "png"
    SVG = "svg"
    JPG = "jpg"
    PDF = "pdf"


class CodeFramework(str, Enum):
    """Code generation framework."""
    REACT = "react"
    REACT_TAILWIND = "react_tailwind"
    VUE = "vue"
    VUE_TAILWIND = "vue_tailwind"
    HTML_CSS = "html_css"
    TAILWIND_ONLY = "tailwind_only"
    CSS = "css"
    SCSS = "scss"
    SWIFTUI = "swiftui"
    KOTLIN = "kotlin"


# ============================================================================
# Pydantic Input Models
# ============================================================================

class FigmaFileInput(BaseModel):
    """Input model for file operations."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(
        ...,
        description="Figma file key (from URL: figma.com/design/FILE_KEY/...)",
        min_length=10,
        max_length=50
    )
    depth: Optional[int] = Field(
        default=2,
        description="Depth of node tree to return (1-10)",
        ge=1,
        le=10
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        # Extract file key from URL if full URL provided
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
            raise ValueError("Could not extract file key from Figma URL")
        return v


class FigmaNodeInput(BaseModel):
    """Input model for node operations."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(
        ...,
        description="Figma file key",
        min_length=10,
        max_length=50
    )
    node_id: str = Field(
        ...,
        description="Node ID (e.g., '1:2' or '1-2')",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
            raise ValueError("Could not extract file key from Figma URL")
        return v

    @field_validator('node_id')
    @classmethod
    def normalize_node_id(cls, v: str) -> str:
        # Convert 1-2 format to 1:2
        return v.replace('-', ':')


class FigmaScreenshotInput(BaseModel):
    """Input model for screenshot operations."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_ids: List[str] = Field(
        ...,
        description="List of node IDs to capture (e.g., ['1:2', '3:4'])",
        min_length=1,
        max_length=10
    )
    format: ImageFormat = Field(
        default=ImageFormat.PNG,
        description="Image format: 'png', 'svg', 'jpg', 'pdf'"
    )
    scale: float = Field(
        default=2.0,
        description="Scale factor (0.01 to 4.0)",
        ge=0.01,
        le=4.0
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v

    @field_validator('node_ids')
    @classmethod
    def normalize_node_ids(cls, v: List[str]) -> List[str]:
        return [nid.replace('-', ':') for nid in v]


class FigmaDesignTokensInput(BaseModel):
    """Input model for design token extraction."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_id: Optional[str] = Field(
        default=None,
        description="Optional node ID to extract tokens from specific component"
    )
    include_colors: bool = Field(default=True, description="Include color tokens")
    include_typography: bool = Field(default=True, description="Include typography tokens")
    include_spacing: bool = Field(default=True, description="Include spacing/padding tokens")
    include_effects: bool = Field(default=True, description="Include shadow/blur effects")

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v


class FigmaCodeGenInput(BaseModel):
    """Input model for code generation."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_id: str = Field(..., description="Node ID to generate code for")
    framework: CodeFramework = Field(
        default=CodeFramework.REACT_TAILWIND,
        description="Target framework"
    )
    component_name: Optional[str] = Field(
        default=None,
        description="Component name (auto-generated from node name if not provided)"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v

    @field_validator('node_id')
    @classmethod
    def normalize_node_id(cls, v: str) -> str:
        return v.replace('-', ':')


class FigmaColorsInput(BaseModel):
    """Input model for color extraction."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_id: Optional[str] = Field(
        default=None,
        description="Optional node ID to extract colors from specific component"
    )
    include_fills: bool = Field(default=True, description="Include fill colors")
    include_strokes: bool = Field(default=True, description="Include stroke colors")
    include_shadows: bool = Field(default=True, description="Include shadow colors")

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v

    @field_validator('node_id')
    @classmethod
    def normalize_node_id(cls, v: Optional[str]) -> Optional[str]:
        return v.replace('-', ':') if v else None


class FigmaTypographyInput(BaseModel):
    """Input model for typography extraction."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_id: Optional[str] = Field(
        default=None,
        description="Optional node ID to extract typography from specific component"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v

    @field_validator('node_id')
    @classmethod
    def normalize_node_id(cls, v: Optional[str]) -> Optional[str]:
        return v.replace('-', ':') if v else None


class FigmaSpacingInput(BaseModel):
    """Input model for spacing extraction."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    node_id: Optional[str] = Field(
        default=None,
        description="Optional node ID to extract spacing from specific component"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v

    @field_validator('node_id')
    @classmethod
    def normalize_node_id(cls, v: Optional[str]) -> Optional[str]:
        return v.replace('-', ':') if v else None


# ============================================================================
# Helper Functions
# ============================================================================

def _get_figma_token() -> str:
    """Get Figma API token from environment."""
    token = os.environ.get("FIGMA_ACCESS_TOKEN") or os.environ.get("FIGMA_TOKEN")
    if not token:
        raise ValueError(
            "Figma API token not found. Set FIGMA_ACCESS_TOKEN or FIGMA_TOKEN environment variable. "
            "Get your token from: https://www.figma.com/developers/api#access-tokens"
        )
    return token


async def _make_figma_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make authenticated request to Figma API."""
    token = _get_figma_token()

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{FIGMA_API_BASE}/{endpoint}",
            headers={"X-Figma-Token": token},
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()


def _handle_api_error(e: Exception) -> str:
    """Format API errors for user-friendly messages."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return "Error: Invalid Figma API token. Check your FIGMA_ACCESS_TOKEN environment variable."
        elif status == 403:
            return "Error: Access denied. You don't have permission to view this file."
        elif status == 404:
            return "Error: File or node not found. Check the file key and node ID."
        elif status == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        return f"Error: Figma API returned status {status}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The file might be too large."
    elif isinstance(e, ValueError):
        return f"Error: {str(e)}"
    return f"Error: {type(e).__name__}: {str(e)}"


def _rgba_to_hex(color: Dict[str, float]) -> str:
    """Convert Figma RGBA color to hex."""
    r = int(color.get('r', 0) * 255)
    g = int(color.get('g', 0) * 255)
    b = int(color.get('b', 0) * 255)
    a = color.get('a', 1)

    if a < 1:
        return f"rgba({r}, {g}, {b}, {a:.2f})"
    return f"#{r:02x}{g:02x}{b:02x}"


def _extract_colors_from_node(node: Dict[str, Any], colors: List[Dict[str, Any]]) -> None:
    """Recursively extract colors from node tree."""
    # Fill colors
    fills = node.get('fills', [])
    for fill in fills:
        if fill.get('type') == 'SOLID' and fill.get('visible', True):
            color = fill.get('color', {})
            colors.append({
                'name': node.get('name', 'Unknown'),
                'type': 'fill',
                'value': _rgba_to_hex(color),
                'opacity': fill.get('opacity', 1)
            })

    # Stroke colors
    strokes = node.get('strokes', [])
    for stroke in strokes:
        if stroke.get('type') == 'SOLID' and stroke.get('visible', True):
            color = stroke.get('color', {})
            colors.append({
                'name': node.get('name', 'Unknown'),
                'type': 'stroke',
                'value': _rgba_to_hex(color),
                'opacity': stroke.get('opacity', 1)
            })

    # Recurse into children
    for child in node.get('children', []):
        _extract_colors_from_node(child, colors)


def _extract_typography_from_node(node: Dict[str, Any], typography: List[Dict[str, Any]]) -> None:
    """Recursively extract typography from node tree."""
    if node.get('type') == 'TEXT':
        style = node.get('style', {})
        typography.append({
            'name': node.get('name', 'Unknown'),
            'fontFamily': style.get('fontFamily', 'Unknown'),
            'fontWeight': style.get('fontWeight', 400),
            'fontSize': style.get('fontSize', 16),
            'lineHeight': style.get('lineHeightPx'),
            'letterSpacing': style.get('letterSpacing', 0),
            'textAlign': style.get('textAlignHorizontal', 'LEFT')
        })

    for child in node.get('children', []):
        _extract_typography_from_node(child, typography)


def _extract_spacing_from_node(node: Dict[str, Any], spacing: List[Dict[str, Any]]) -> None:
    """Recursively extract spacing/padding from node tree."""
    # Auto-layout padding
    if 'paddingLeft' in node or 'itemSpacing' in node:
        spacing.append({
            'name': node.get('name', 'Unknown'),
            'type': 'auto-layout',
            'paddingTop': node.get('paddingTop', 0),
            'paddingRight': node.get('paddingRight', 0),
            'paddingBottom': node.get('paddingBottom', 0),
            'paddingLeft': node.get('paddingLeft', 0),
            'itemSpacing': node.get('itemSpacing', 0),
            'layoutMode': node.get('layoutMode', 'NONE')
        })

    # Absolute bounds
    bbox = node.get('absoluteBoundingBox', {})
    if bbox:
        spacing.append({
            'name': node.get('name', 'Unknown'),
            'type': 'bounds',
            'width': bbox.get('width', 0),
            'height': bbox.get('height', 0),
            'x': bbox.get('x', 0),
            'y': bbox.get('y', 0)
        })

    for child in node.get('children', []):
        _extract_spacing_from_node(child, spacing)


def _extract_shadows_from_node(node: Dict[str, Any], shadows: List[Dict[str, Any]]) -> None:
    """Recursively extract shadow colors from node tree."""
    effects = node.get('effects', [])
    for effect in effects:
        if 'SHADOW' in effect.get('type', '') and effect.get('visible', True):
            color = effect.get('color', {})
            shadows.append({
                'name': node.get('name', 'Unknown'),
                'type': effect.get('type'),
                'hex': _rgba_to_hex(color),
                'rgba': f"rgba({int(color.get('r', 0) * 255)}, {int(color.get('g', 0) * 255)}, {int(color.get('b', 0) * 255)}, {color.get('a', 1):.2f})",
                'offset': effect.get('offset', {'x': 0, 'y': 0}),
                'radius': effect.get('radius', 0),
                'spread': effect.get('spread', 0)
            })

    for child in node.get('children', []):
        _extract_shadows_from_node(child, shadows)


def _get_node_with_children(file_key: str, node_id: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
    """Get node with all children from file data."""
    if node_id:
        # Find node in document tree
        def find_node(node: Dict[str, Any], target_id: str) -> Optional[Dict[str, Any]]:
            if node.get('id') == target_id:
                return node
            for child in node.get('children', []):
                result = find_node(child, target_id)
                if result:
                    return result
            return None
        return find_node(data.get('document', {}), node_id) or {}
    return data.get('document', {})


def _node_to_simplified_tree(node: Dict[str, Any], depth: int, current_depth: int = 0) -> Dict[str, Any]:
    """Convert Figma node to simplified tree structure."""
    simplified = {
        'id': node.get('id'),
        'name': node.get('name'),
        'type': node.get('type')
    }

    # Add bounds if available
    bbox = node.get('absoluteBoundingBox')
    if bbox:
        simplified['bounds'] = {
            'width': round(bbox.get('width', 0)),
            'height': round(bbox.get('height', 0))
        }

    # Add children if within depth limit
    if current_depth < depth and 'children' in node:
        simplified['children'] = [
            _node_to_simplified_tree(child, depth, current_depth + 1)
            for child in node.get('children', [])
        ]

    return simplified


def _generate_react_code(node: Dict[str, Any], component_name: str, use_tailwind: bool = True) -> str:
    """Generate detailed React component code from Figma node with all nested children."""
    # Generate the inner JSX content recursively
    inner_jsx = _recursive_node_to_jsx(node, indent=6, use_tailwind=use_tailwind)

    if use_tailwind:
        code = f'''import React from 'react';

interface {component_name}Props {{
  className?: string;
}}

export const {component_name}: React.FC<{component_name}Props> = ({{
  className = '',
}}) => {{
  return (
{inner_jsx}
  );
}};

export default {component_name};
'''
    else:
        code = f'''import React from 'react';

interface {component_name}Props {{
  className?: string;
}}

export const {component_name}: React.FC<{component_name}Props> = ({{
  className = '',
}}) => {{
  return (
{inner_jsx}
  );
}};

export default {component_name};
'''
    return code


def _recursive_node_to_vue_template(node: Dict[str, Any], indent: int = 4, use_tailwind: bool = True) -> str:
    """Recursively generate Vue template code for nested children."""
    lines = []
    prefix = ' ' * indent
    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')

    bbox = node.get('absoluteBoundingBox', {})
    width = int(bbox.get('width', 0))
    height = int(bbox.get('height', 0))

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        bg_color = _rgba_to_hex(fills[0].get('color', {}))

    strokes = node.get('strokes', [])
    stroke_color = ''
    stroke_weight = node.get('strokeWeight', 0)
    if strokes and strokes[0].get('type') == 'SOLID' and strokes[0].get('visible', True):
        stroke_color = _rgba_to_hex(strokes[0].get('color', {}))

    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    if node_type == 'TEXT':
        text = node.get('characters', name)
        style = node.get('style', {})
        font_size = style.get('fontSize', 16)
        font_weight = style.get('fontWeight', 400)

        text_color = ''
        if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
            text_color = _rgba_to_hex(fills[0].get('color', {}))

        if use_tailwind:
            weight_map = {300: 'font-light', 400: 'font-normal', 500: 'font-medium', 600: 'font-semibold', 700: 'font-bold'}
            weight_class = weight_map.get(font_weight, 'font-normal')
            classes = [f'text-[{int(font_size)}px]', weight_class]
            if text_color:
                classes.append(f'text-[{text_color}]')
            class_str = ' '.join(filter(None, classes))
            lines.append(f'{prefix}<span class="{class_str}">{text}</span>')
        else:
            lines.append(f'{prefix}<span class="text-{name.lower().replace(" ", "-")}">{text}</span>')
    else:
        if use_tailwind:
            classes = []
            if width:
                classes.append(f'w-[{width}px]')
            if height:
                classes.append(f'h-[{height}px]')
            if bg_color:
                classes.append(f'bg-[{bg_color}]')
            if corner_radius:
                classes.append(f'rounded-[{corner_radius}px]')
            if stroke_color and stroke_weight:
                classes.append(f'border-[{stroke_weight}px]')
                classes.append(f'border-[{stroke_color}]')
            if layout_mode:
                classes.append('flex')
                classes.append('flex-col' if layout_mode == 'VERTICAL' else 'flex-row')
                if gap:
                    classes.append(f'gap-[{gap}px]')
            if padding_top:
                classes.append(f'pt-[{padding_top}px]')
            if padding_right:
                classes.append(f'pr-[{padding_right}px]')
            if padding_bottom:
                classes.append(f'pb-[{padding_bottom}px]')
            if padding_left:
                classes.append(f'pl-[{padding_left}px]')

            class_str = ' '.join(filter(None, classes))
            lines.append(f'{prefix}<div class="{class_str}">')
        else:
            class_name = name.lower().replace(' ', '-').replace('/', '-')
            lines.append(f'{prefix}<div class="{class_name}">')

        children = node.get('children', [])
        for child in children[:20]:
            child_template = _recursive_node_to_vue_template(child, indent + 2, use_tailwind)
            if child_template:
                lines.append(child_template)

        lines.append(f'{prefix}</div>')

    return '\n'.join(lines)


def _generate_vue_code(node: Dict[str, Any], component_name: str, use_tailwind: bool = True) -> str:
    """Generate detailed Vue component code from Figma node with all nested children."""
    inner_template = _recursive_node_to_vue_template(node, indent=4, use_tailwind=use_tailwind)

    if use_tailwind:
        code = f'''<script setup lang="ts">
defineProps<{{
  class?: string;
}}>();
</script>

<template>
{inner_template}
</template>
'''
    else:
        # Generate CSS for all nodes
        css_rules = _generate_recursive_css(node, [])
        css_code = '\n'.join(css_rules)

        code = f'''<script setup lang="ts">
defineProps<{{
  class?: string;
}}>();
</script>

<template>
{inner_template}
</template>

<style scoped>
{css_code}
</style>
'''
    return code


def _generate_recursive_css(node: Dict[str, Any], rules: List[str], parent_name: str = '') -> List[str]:
    """Generate CSS rules for all nodes recursively."""
    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')
    class_name = name.lower().replace(' ', '-').replace('/', '-')

    bbox = node.get('absoluteBoundingBox', {})
    width = int(bbox.get('width', 0))
    height = int(bbox.get('height', 0))

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        bg_color = _rgba_to_hex(fills[0].get('color', {}))

    strokes = node.get('strokes', [])
    stroke_css = ''
    if strokes and strokes[0].get('type') == 'SOLID' and strokes[0].get('visible', True):
        stroke_color = _rgba_to_hex(strokes[0].get('color', {}))
        stroke_weight = node.get('strokeWeight', 1)
        stroke_css = f"border: {stroke_weight}px solid {stroke_color};"

    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    css_props = []
    if width:
        css_props.append(f"width: {width}px;")
    if height:
        css_props.append(f"height: {height}px;")
    if bg_color:
        css_props.append(f"background-color: {bg_color};")
    if corner_radius:
        css_props.append(f"border-radius: {corner_radius}px;")
    if stroke_css:
        css_props.append(stroke_css)
    if layout_mode:
        css_props.append("display: flex;")
        css_props.append(f"flex-direction: {'column' if layout_mode == 'VERTICAL' else 'row'};")
        if gap:
            css_props.append(f"gap: {gap}px;")
    if padding_top or padding_right or padding_bottom or padding_left:
        css_props.append(f"padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;")

    if node_type == 'TEXT':
        style = node.get('style', {})
        font_size = style.get('fontSize', 16)
        font_weight = style.get('fontWeight', 400)
        text_color = ''
        if fills and fills[0].get('type') == 'SOLID':
            text_color = _rgba_to_hex(fills[0].get('color', {}))

        css_props = [f"font-size: {int(font_size)}px;", f"font-weight: {font_weight};"]
        if text_color:
            css_props.append(f"color: {text_color};")

    if css_props:
        rule = f".{class_name} {{\n  " + "\n  ".join(css_props) + "\n}"
        rules.append(rule)

    for child in node.get('children', [])[:20]:
        _generate_recursive_css(child, rules, class_name)

    return rules


def _generate_css_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate pure CSS code from Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 'auto')
    height = bbox.get('height', 'auto')

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        bg_color = _rgba_to_hex(fills[0].get('color', {}))

    # Strokes
    strokes = node.get('strokes', [])
    stroke_css = ''
    if strokes and strokes[0].get('type') == 'SOLID':
        stroke_color = _rgba_to_hex(strokes[0].get('color', {}))
        stroke_weight = node.get('strokeWeight', 1)
        stroke_css = f"border: {stroke_weight}px solid {stroke_color};"

    # Border radius
    corner_radius = node.get('cornerRadius', 0)
    radius_css = f"border-radius: {corner_radius}px;" if corner_radius else ''

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
        layout_css = f"""display: flex;
  flex-direction: {direction};
  gap: {gap}px;
  padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;"""

    # Effects (shadows)
    effects = node.get('effects', [])
    shadow_css = ''
    for effect in effects:
        if 'SHADOW' in effect.get('type', '') and effect.get('visible', True):
            color = effect.get('color', {})
            offset = effect.get('offset', {'x': 0, 'y': 0})
            radius = effect.get('radius', 0)
            shadow_css = f"box-shadow: {offset.get('x', 0)}px {offset.get('y', 0)}px {radius}px {_rgba_to_hex(color)};"
            break

    code = f'''.{component_name.lower()} {{
  width: {int(width)}px;
  height: {int(height)}px;
  {f"background-color: {bg_color};" if bg_color else ''}
  {stroke_css}
  {radius_css}
  {layout_css}
  {shadow_css}
}}'''
    return code


def _generate_scss_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate SCSS code with variables from Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 'auto')
    height = bbox.get('height', 'auto')

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        bg_color = _rgba_to_hex(fills[0].get('color', {}))

    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    variables = f'''// {component_name} Variables
$width: {int(width)}px;
$height: {int(height)}px;
{f"$bg-color: {bg_color};" if bg_color else ''}
$border-radius: {corner_radius}px;
$gap: {gap}px;
$padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;
'''

    direction = 'column' if layout_mode == 'VERTICAL' else 'row' if layout_mode else ''
    layout_scss = f'''display: flex;
    flex-direction: {direction};
    gap: $gap;
    padding: $padding;''' if layout_mode else ''

    code = f'''{variables}

.{component_name.lower()} {{
  width: $width;
  height: $height;
  {f"background-color: $bg-color;" if bg_color else ''}
  border-radius: $border-radius;
  {layout_scss}
}}'''
    return code


def _generate_swiftui_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate SwiftUI code from Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 100)
    height = bbox.get('height', 100)

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        color = fills[0].get('color', {})
        r = color.get('r', 0)
        g = color.get('g', 0)
        b = color.get('b', 0)
        a = color.get('a', 1)
        bg_color = f"Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}, opacity: {a:.2f})"

    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Determine container type
    container = 'VStack' if layout_mode == 'VERTICAL' else 'HStack' if layout_mode == 'HORIZONTAL' else 'ZStack'
    spacing = f"spacing: {gap}" if gap else ''

    # Generate children
    children_code = _generate_swiftui_children(node.get('children', []))

    code = f'''import SwiftUI

struct {component_name}: View {{
    var body: some View {{
        {container}({spacing}) {{
{children_code if children_code else '            // Content'}
        }}
        .frame(width: {int(width)}, height: {int(height)})
        {f".background({bg_color})" if bg_color else ''}
        {f".cornerRadius({corner_radius})" if corner_radius else ''}
        .padding(.top, {padding_top})
        .padding(.trailing, {padding_right})
        .padding(.bottom, {padding_bottom})
        .padding(.leading, {padding_left})
    }}
}}

#Preview {{
    {component_name}()
}}
'''
    return code


def _generate_swiftui_children(children: List[Dict[str, Any]], indent: int = 12) -> str:
    """Generate SwiftUI code for children nodes."""
    lines = []
    prefix = ' ' * indent

    for child in children[:10]:  # Limit to 10 children
        node_type = child.get('type', '')
        name = child.get('name', 'Unknown')

        if node_type == 'TEXT':
            text = child.get('characters', name)
            style = child.get('style', {})
            font_size = style.get('fontSize', 16)
            font_weight = style.get('fontWeight', 400)
            weight_map = {300: '.light', 400: '.regular', 500: '.medium', 600: '.semibold', 700: '.bold'}
            weight = weight_map.get(font_weight, '.regular')
            lines.append(f'{prefix}Text("{text}")')
            lines.append(f'{prefix}    .font(.system(size: {font_size}, weight: {weight}))')
        elif node_type in ['FRAME', 'GROUP', 'COMPONENT', 'INSTANCE']:
            bbox = child.get('absoluteBoundingBox', {})
            w = bbox.get('width', 50)
            h = bbox.get('height', 50)

            fills = child.get('fills', [])
            if fills and fills[0].get('type') == 'SOLID':
                color = fills[0].get('color', {})
                lines.append(f'{prefix}Rectangle()')
                lines.append(f'{prefix}    .fill(Color(red: {color.get("r", 0):.3f}, green: {color.get("g", 0):.3f}, blue: {color.get("b", 0):.3f}))')
                lines.append(f'{prefix}    .frame(width: {int(w)}, height: {int(h)})')
            else:
                lines.append(f'{prefix}// {name}')
                lines.append(f'{prefix}Rectangle()')
                lines.append(f'{prefix}    .frame(width: {int(w)}, height: {int(h)})')
        elif node_type == 'RECTANGLE':
            bbox = child.get('absoluteBoundingBox', {})
            w = bbox.get('width', 50)
            h = bbox.get('height', 50)
            lines.append(f'{prefix}Rectangle()')
            lines.append(f'{prefix}    .frame(width: {int(w)}, height: {int(h)})')

    return '\n'.join(lines)


def _generate_kotlin_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate Kotlin Jetpack Compose code from Figma node."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 100)
    height = bbox.get('height', 100)

    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        color = fills[0].get('color', {})
        r = int(color.get('r', 0) * 255)
        g = int(color.get('g', 0) * 255)
        b = int(color.get('b', 0) * 255)
        a = color.get('a', 1)
        bg_color = f"Color(0x{int(a*255):02X}{r:02X}{g:02X}{b:02X})"

    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Determine container type
    container = 'Column' if layout_mode == 'VERTICAL' else 'Row' if layout_mode == 'HORIZONTAL' else 'Box'

    # Generate children
    children_code = _generate_kotlin_children(node.get('children', []))

    arrangement = f"verticalArrangement = Arrangement.spacedBy({gap}.dp)" if layout_mode == 'VERTICAL' and gap else \
                  f"horizontalArrangement = Arrangement.spacedBy({gap}.dp)" if layout_mode == 'HORIZONTAL' and gap else ''

    code = f'''package com.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun {component_name}(
    modifier: Modifier = Modifier
) {{
    {container}(
        modifier = modifier
            .width({int(width)}.dp)
            .height({int(height)}.dp)
            {f".background({bg_color})" if bg_color else ''}
            {f".clip(RoundedCornerShape({corner_radius}.dp))" if corner_radius else ''}
            .padding(
                top = {padding_top}.dp,
                end = {padding_right}.dp,
                bottom = {padding_bottom}.dp,
                start = {padding_left}.dp
            ),
        {arrangement}
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


def _generate_kotlin_children(children: List[Dict[str, Any]], indent: int = 8) -> str:
    """Generate Kotlin Compose code for children nodes."""
    lines = []
    prefix = ' ' * indent

    for child in children[:10]:  # Limit to 10 children
        node_type = child.get('type', '')
        name = child.get('name', 'Unknown')

        if node_type == 'TEXT':
            text = child.get('characters', name)
            style = child.get('style', {})
            font_size = style.get('fontSize', 16)
            lines.append(f'{prefix}Text(')
            lines.append(f'{prefix}    text = "{text}",')
            lines.append(f'{prefix}    fontSize = {int(font_size)}.sp')
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


def _recursive_node_to_jsx(node: Dict[str, Any], indent: int = 6, use_tailwind: bool = True) -> str:
    """Recursively generate detailed JSX code for nested children with all styles."""
    lines = []
    prefix = ' ' * indent
    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')

    # Get all styles
    bbox = node.get('absoluteBoundingBox', {})
    width = int(bbox.get('width', 0))
    height = int(bbox.get('height', 0))

    # Fills
    fills = node.get('fills', [])
    bg_color = ''
    if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
        bg_color = _rgba_to_hex(fills[0].get('color', {}))

    # Strokes
    strokes = node.get('strokes', [])
    stroke_color = ''
    stroke_weight = node.get('strokeWeight', 0)
    if strokes and strokes[0].get('type') == 'SOLID' and strokes[0].get('visible', True):
        stroke_color = _rgba_to_hex(strokes[0].get('color', {}))

    # Effects (shadows)
    effects = node.get('effects', [])
    shadow_css = ''
    for effect in effects:
        if 'SHADOW' in effect.get('type', '') and effect.get('visible', True):
            color = effect.get('color', {})
            offset = effect.get('offset', {'x': 0, 'y': 0})
            radius = effect.get('radius', 0)
            spread = effect.get('spread', 0)
            shadow_color = _rgba_to_hex(color)
            shadow_css = f"{int(offset.get('x', 0))}px {int(offset.get('y', 0))}px {int(radius)}px {int(spread)}px {shadow_color}"
            break

    # Layout
    corner_radius = node.get('cornerRadius', 0)
    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Alignment
    primary_align = node.get('primaryAxisAlignItems', 'MIN')
    counter_align = node.get('counterAxisAlignItems', 'MIN')

    if node_type == 'TEXT':
        text = node.get('characters', name)
        style = node.get('style', {})
        font_size = style.get('fontSize', 16)
        font_weight = style.get('fontWeight', 400)
        font_family = style.get('fontFamily', '')
        line_height = style.get('lineHeightPx')
        letter_spacing = style.get('letterSpacing', 0)
        text_align = style.get('textAlignHorizontal', 'LEFT').lower()

        # Get text color from fills
        text_color = ''
        if fills and fills[0].get('type') == 'SOLID' and fills[0].get('visible', True):
            text_color = _rgba_to_hex(fills[0].get('color', {}))

        if use_tailwind:
            weight_map = {300: 'font-light', 400: 'font-normal', 500: 'font-medium', 600: 'font-semibold', 700: 'font-bold', 800: 'font-extrabold', 900: 'font-black'}
            weight_class = weight_map.get(font_weight, 'font-normal')
            align_map = {'left': 'text-left', 'center': 'text-center', 'right': 'text-right', 'justified': 'text-justify'}
            align_class = align_map.get(text_align, '')

            classes = [f'text-[{int(font_size)}px]', weight_class]
            if text_color:
                classes.append(f'text-[{text_color}]')
            if line_height:
                classes.append(f'leading-[{int(line_height)}px]')
            if letter_spacing:
                classes.append(f'tracking-[{letter_spacing:.2f}px]')
            if align_class:
                classes.append(align_class)

            class_str = ' '.join(filter(None, classes))
            # Escape text for JSX
            escaped_text = text.replace('{', '{{').replace('}', '}}').replace('<', '&lt;').replace('>', '&gt;')
            lines.append(f'{prefix}<span className="{class_str}">{escaped_text}</span>')
        else:
            styles = [f"fontSize: '{int(font_size)}px'", f"fontWeight: {font_weight}"]
            if text_color:
                styles.append(f"color: '{text_color}'")
            if font_family:
                styles.append(f"fontFamily: '{font_family}'")
            if line_height:
                styles.append(f"lineHeight: '{int(line_height)}px'")
            if letter_spacing:
                styles.append(f"letterSpacing: '{letter_spacing:.2f}px'")
            if text_align != 'left':
                styles.append(f"textAlign: '{text_align}'")

            style_str = ', '.join(styles)
            escaped_text = text.replace('{', '{{').replace('}', '}}').replace('<', '&lt;').replace('>', '&gt;')
            lines.append(f'{prefix}<span style={{{{ {style_str} }}}}>{escaped_text}</span>')

    elif node_type == 'VECTOR' or node_type == 'BOOLEAN_OPERATION':
        # For vector/icon nodes, create a placeholder or use SVG
        if use_tailwind:
            classes = []
            if width:
                classes.append(f'w-[{width}px]')
            if height:
                classes.append(f'h-[{height}px]')
            if bg_color:
                classes.append(f'bg-[{bg_color}]')
            class_str = ' '.join(filter(None, classes))
            lines.append(f'{prefix}{{/* Icon: {name} */}}')
            lines.append(f'{prefix}<div className="{class_str}" />')
        else:
            lines.append(f'{prefix}{{/* Icon: {name} */}}')
            lines.append(f'{prefix}<div style={{{{ width: "{width}px", height: "{height}px" }}}} />')

    else:
        # Container element (FRAME, GROUP, COMPONENT, INSTANCE, RECTANGLE, etc.)
        if use_tailwind:
            classes = []
            if width:
                classes.append(f'w-[{width}px]')
            if height:
                classes.append(f'h-[{height}px]')
            if bg_color:
                classes.append(f'bg-[{bg_color}]')
            if corner_radius:
                classes.append(f'rounded-[{corner_radius}px]')
            if stroke_color and stroke_weight:
                classes.append(f'border-[{stroke_weight}px]')
                classes.append(f'border-[{stroke_color}]')
            if shadow_css:
                classes.append(f'shadow-[{shadow_css}]')
            if layout_mode:
                classes.append('flex')
                classes.append('flex-col' if layout_mode == 'VERTICAL' else 'flex-row')
                if gap:
                    classes.append(f'gap-[{gap}px]')
                # Alignment
                justify_map = {'MIN': 'justify-start', 'CENTER': 'justify-center', 'MAX': 'justify-end', 'SPACE_BETWEEN': 'justify-between'}
                items_map = {'MIN': 'items-start', 'CENTER': 'items-center', 'MAX': 'items-end'}
                classes.append(justify_map.get(primary_align, ''))
                classes.append(items_map.get(counter_align, ''))
            if padding_top or padding_right or padding_bottom or padding_left:
                if padding_top:
                    classes.append(f'pt-[{padding_top}px]')
                if padding_right:
                    classes.append(f'pr-[{padding_right}px]')
                if padding_bottom:
                    classes.append(f'pb-[{padding_bottom}px]')
                if padding_left:
                    classes.append(f'pl-[{padding_left}px]')

            class_str = ' '.join(filter(None, classes))
            lines.append(f'{prefix}<div className="{class_str}">')
        else:
            styles = []
            if width:
                styles.append(f"width: '{width}px'")
            if height:
                styles.append(f"height: '{height}px'")
            if bg_color:
                styles.append(f"backgroundColor: '{bg_color}'")
            if corner_radius:
                styles.append(f"borderRadius: '{corner_radius}px'")
            if stroke_color and stroke_weight:
                styles.append(f"border: '{stroke_weight}px solid {stroke_color}'")
            if shadow_css:
                styles.append(f"boxShadow: '{shadow_css}'")
            if layout_mode:
                styles.append("display: 'flex'")
                styles.append(f"flexDirection: '{'column' if layout_mode == 'VERTICAL' else 'row'}'")
                if gap:
                    styles.append(f"gap: '{gap}px'")
                # Alignment
                justify_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}
                items_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end'}
                styles.append(f"justifyContent: '{justify_map.get(primary_align, 'flex-start')}'")
                styles.append(f"alignItems: '{items_map.get(counter_align, 'flex-start')}'")
            if padding_top or padding_right or padding_bottom or padding_left:
                styles.append(f"padding: '{padding_top}px {padding_right}px {padding_bottom}px {padding_left}px'")

            style_str = ', '.join(styles)
            lines.append(f'{prefix}<div style={{{{ {style_str} }}}}>')

        # Recursively add children
        children = node.get('children', [])
        for child in children[:20]:  # Limit to 20 children for safety
            child_jsx = _recursive_node_to_jsx(child, indent + 2, use_tailwind)
            if child_jsx:
                lines.append(child_jsx)

        lines.append(f'{prefix}</div>')

    return '\n'.join(lines)


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool(
    name="figma_get_file_structure",
    annotations={
        "title": "Get Figma File Structure",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_file_structure(params: FigmaFileInput) -> str:
    """
    Get the structure and node tree of a Figma file.

    This tool retrieves the hierarchical structure of a Figma file, including
    all pages, frames, components, and their relationships.

    Args:
        params: FigmaFileInput containing:
            - file_key (str): Figma file key or full URL
            - depth (int): How deep to traverse the node tree (1-10)
            - response_format: 'markdown' or 'json'

    Returns:
        str: File structure in requested format

    Examples:
        - "Get structure of file XYZ123" -> file_key="XYZ123", depth=2
        - Full URL works too: file_key="https://figma.com/design/XYZ123/MyFile"
    """
    try:
        data = await _make_figma_request(f"files/{params.file_key}")

        document = data.get('document', {})
        name = data.get('name', 'Unknown')
        last_modified = data.get('lastModified', 'Unknown')

        # Build simplified tree
        tree = _node_to_simplified_tree(document, params.depth)

        if params.response_format == ResponseFormat.JSON:
            response = {
                'name': name,
                'lastModified': last_modified,
                'document': tree
            }
            return json.dumps(response, indent=2)

        # Markdown format
        lines = [
            f"# Figma File: {name}",
            f"**Last Modified:** {last_modified}",
            f"**File Key:** `{params.file_key}`",
            "",
            "## Document Structure",
            ""
        ]

        def format_tree(node: Dict, indent: int = 0) -> None:
            prefix = "  " * indent
            icon = "📄" if node.get('type') == 'DOCUMENT' else \
                   "📑" if node.get('type') == 'CANVAS' else \
                   "🖼️" if node.get('type') == 'FRAME' else \
                   "📦" if node.get('type') == 'COMPONENT' else \
                   "🔗" if node.get('type') == 'INSTANCE' else \
                   "📝" if node.get('type') == 'TEXT' else "•"

            bounds = node.get('bounds', {})
            size_str = f" ({bounds.get('width')}×{bounds.get('height')})" if bounds else ""

            lines.append(f"{prefix}{icon} **{node.get('name')}** `{node.get('id')}`{size_str}")

            for child in node.get('children', []):
                format_tree(child, indent + 1)

        format_tree(tree)

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_node_details",
    annotations={
        "title": "Get Figma Node Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_node_details(params: FigmaNodeInput) -> str:
    """
    Get detailed information about a specific node in a Figma file.

    Retrieves comprehensive details including styles, fills, strokes,
    effects, and layout properties for a specific node.

    Args:
        params: FigmaNodeInput containing:
            - file_key (str): Figma file key
            - node_id (str): Node ID (e.g., '1:2' or '1-2')
            - response_format: 'markdown' or 'json'

    Returns:
        str: Node details in requested format
    """
    try:
        data = await _make_figma_request(
            f"files/{params.file_key}/nodes",
            params={"ids": params.node_id}
        )

        nodes = data.get('nodes', {})
        node_data = nodes.get(params.node_id, {})
        node = node_data.get('document', {})

        if not node:
            return f"Error: Node '{params.node_id}' not found in file."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(node, indent=2)

        # Markdown format
        lines = [
            f"# Node: {node.get('name', 'Unknown')}",
            f"**ID:** `{params.node_id}`",
            f"**Type:** {node.get('type')}",
            ""
        ]

        # Bounds
        bbox = node.get('absoluteBoundingBox', {})
        if bbox:
            lines.extend([
                "## Dimensions",
                f"- **Width:** {bbox.get('width', 0):.0f}px",
                f"- **Height:** {bbox.get('height', 0):.0f}px",
                f"- **Position:** ({bbox.get('x', 0):.0f}, {bbox.get('y', 0):.0f})",
                ""
            ])

        # Fills
        fills = node.get('fills', [])
        if fills:
            lines.append("## Fills")
            for fill in fills:
                if fill.get('type') == 'SOLID':
                    color = fill.get('color', {})
                    lines.append(f"- {_rgba_to_hex(color)} (opacity: {fill.get('opacity', 1):.2f})")
                elif fill.get('type') == 'GRADIENT_LINEAR':
                    lines.append(f"- Linear gradient")
            lines.append("")

        # Strokes
        strokes = node.get('strokes', [])
        if strokes:
            lines.append("## Strokes")
            stroke_weight = node.get('strokeWeight', 1)
            for stroke in strokes:
                if stroke.get('type') == 'SOLID':
                    color = stroke.get('color', {})
                    lines.append(f"- {_rgba_to_hex(color)} ({stroke_weight}px)")
            lines.append("")

        # Effects (shadows, blur)
        effects = node.get('effects', [])
        if effects:
            lines.append("## Effects")
            for effect in effects:
                effect_type = effect.get('type', '')
                if 'SHADOW' in effect_type:
                    color = effect.get('color', {})
                    offset = effect.get('offset', {})
                    radius = effect.get('radius', 0)
                    lines.append(
                        f"- Shadow: {_rgba_to_hex(color)}, "
                        f"offset ({offset.get('x', 0)}, {offset.get('y', 0)}), "
                        f"blur {radius}px"
                    )
                elif effect_type == 'LAYER_BLUR':
                    lines.append(f"- Blur: {effect.get('radius', 0)}px")
            lines.append("")

        # Auto-layout
        if node.get('layoutMode'):
            lines.extend([
                "## Auto Layout",
                f"- **Mode:** {node.get('layoutMode')}",
                f"- **Padding:** {node.get('paddingTop', 0)} {node.get('paddingRight', 0)} {node.get('paddingBottom', 0)} {node.get('paddingLeft', 0)}",
                f"- **Item Spacing:** {node.get('itemSpacing', 0)}",
                ""
            ])

        # Corner radius
        corner_radius = node.get('cornerRadius')
        if corner_radius:
            lines.extend([
                "## Border Radius",
                f"- **Radius:** {corner_radius}px",
                ""
            ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_screenshot",
    annotations={
        "title": "Get Figma Screenshot",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_screenshot(params: FigmaScreenshotInput) -> str:
    """
    Export screenshot/image of specific nodes from a Figma file.

    Renders the specified nodes as images in the requested format.
    Returns URLs that can be used to download the images (valid for 30 days).

    Args:
        params: FigmaScreenshotInput containing:
            - file_key (str): Figma file key
            - node_ids (List[str]): List of node IDs to capture
            - format: 'png', 'svg', 'jpg', 'pdf'
            - scale (float): Scale factor (0.01 to 4.0)

    Returns:
        str: Image URLs for each requested node
    """
    try:
        ids = ",".join(params.node_ids)

        data = await _make_figma_request(
            f"images/{params.file_key}",
            params={
                "ids": ids,
                "format": params.format.value,
                "scale": params.scale
            }
        )

        images = data.get('images', {})

        if not images:
            return "Error: No images were generated. Check the node IDs."

        lines = [
            "# Generated Screenshots",
            f"**Format:** {params.format.value.upper()}",
            f"**Scale:** {params.scale}x",
            "",
            "## Image URLs",
            ""
        ]

        for node_id, url in images.items():
            if url:
                lines.append(f"- **{node_id}**: [Download]({url})")
            else:
                lines.append(f"- **{node_id}**: ⚠️ Failed to render")

        lines.extend([
            "",
            "> Note: These URLs expire in 30 days."
        ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_design_tokens",
    annotations={
        "title": "Extract Design Tokens",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_design_tokens(params: FigmaDesignTokensInput) -> str:
    """
    Extract design tokens (colors, typography, spacing) from a Figma file.

    Analyzes the file or specific node to extract reusable design tokens
    including colors, font styles, and spacing values.

    Args:
        params: FigmaDesignTokensInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to analyze
            - include_colors, include_typography, include_spacing, include_effects: Toggle token types

    Returns:
        str: JSON formatted design tokens
    """
    try:
        if params.node_id:
            data = await _make_figma_request(
                f"files/{params.file_key}/nodes",
                params={"ids": params.node_id}
            )
            nodes = data.get('nodes', {})
            node = nodes.get(params.node_id, {}).get('document', {})
        else:
            data = await _make_figma_request(f"files/{params.file_key}")
            node = data.get('document', {})

        tokens = {}

        # Extract colors
        if params.include_colors:
            colors: List[Dict[str, Any]] = []
            _extract_colors_from_node(node, colors)
            # Deduplicate by value
            unique_colors = {}
            for c in colors:
                key = c['value']
                if key not in unique_colors:
                    unique_colors[key] = c
            tokens['colors'] = list(unique_colors.values())

        # Extract typography
        if params.include_typography:
            typography: List[Dict[str, Any]] = []
            _extract_typography_from_node(node, typography)
            tokens['typography'] = typography

        # Extract spacing
        if params.include_spacing:
            spacing: List[Dict[str, Any]] = []
            _extract_spacing_from_node(node, spacing)
            # Filter to only auto-layout items
            tokens['spacing'] = [s for s in spacing if s.get('type') == 'auto-layout']

        # Format as design token standard
        formatted_tokens = {
            '$schema': 'https://design-tokens.github.io/community-group/format/',
            'figmaFile': params.file_key,
            'tokens': tokens
        }

        result = json.dumps(formatted_tokens, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            return json.dumps({
                'truncated': True,
                'message': f'Result exceeded {CHARACTER_LIMIT} characters. Try specifying a node_id to narrow scope.',
                'tokens': {k: v[:10] for k, v in tokens.items()} if tokens else {}
            }, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_generate_code",
    annotations={
        "title": "Generate Code from Figma",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_generate_code(params: FigmaCodeGenInput) -> str:
    """
    Generate detailed code from a Figma node with all nested children.

    Converts a Figma design node into production-ready code for the specified framework.
    Includes all nested children, text content, styles (colors, shadows, borders), and layout.

    Supported frameworks:
    - react, react_tailwind: React components with TypeScript
    - vue, vue_tailwind: Vue 3 components with Composition API
    - html_css: Standard HTML with CSS
    - tailwind_only: Just Tailwind CSS classes
    - css: Pure CSS with all styles
    - scss: SCSS with variables and nesting
    - swiftui: iOS SwiftUI Views
    - kotlin: Android Jetpack Compose

    Args:
        params: FigmaCodeGenInput containing:
            - file_key (str): Figma file key
            - node_id (str): Node ID to convert
            - framework: Target framework
            - component_name (Optional[str]): Custom component name

    Returns:
        str: Generated code in the requested framework
    """
    try:
        # Use full file endpoint to get all nested children
        data = await _make_figma_request(f"files/{params.file_key}")
        node = _get_node_with_children(params.file_key, params.node_id, data)

        if not node:
            return f"Error: Node '{params.node_id}' not found."

        # Generate component name
        component_name = params.component_name or node.get('name', 'Component')
        component_name = re.sub(r'[^a-zA-Z0-9]', '', component_name.title())
        if not component_name[0].isalpha():
            component_name = 'Component' + component_name

        # Generate code based on framework
        if params.framework in [CodeFramework.REACT, CodeFramework.REACT_TAILWIND]:
            use_tailwind = params.framework == CodeFramework.REACT_TAILWIND
            code = _generate_react_code(node, component_name, use_tailwind)
        elif params.framework in [CodeFramework.VUE, CodeFramework.VUE_TAILWIND]:
            use_tailwind = params.framework == CodeFramework.VUE_TAILWIND
            code = _generate_vue_code(node, component_name, use_tailwind)
        elif params.framework == CodeFramework.TAILWIND_ONLY:
            bbox = node.get('absoluteBoundingBox', {})
            fills = node.get('fills', [])
            bg = ''
            if fills and fills[0].get('type') == 'SOLID':
                bg = f"bg-[{_rgba_to_hex(fills[0].get('color', {}))}]"
            code = f"w-[{int(bbox.get('width', 0))}px] h-[{int(bbox.get('height', 0))}px] {bg}"
        elif params.framework == CodeFramework.CSS:
            code = _generate_css_code(node, component_name)
        elif params.framework == CodeFramework.SCSS:
            code = _generate_scss_code(node, component_name)
        elif params.framework == CodeFramework.SWIFTUI:
            code = _generate_swiftui_code(node, component_name)
        elif params.framework == CodeFramework.KOTLIN:
            code = _generate_kotlin_code(node, component_name)
        else:
            # HTML/CSS
            bbox = node.get('absoluteBoundingBox', {})
            fills = node.get('fills', [])
            bg = ''
            if fills and fills[0].get('type') == 'SOLID':
                bg = f"background-color: {_rgba_to_hex(fills[0].get('color', {}))};"

            code = f'''<!-- {component_name} -->
<div class="{component_name.lower()}">
  <!-- Content -->
</div>

<style>
.{component_name.lower()} {{
  width: {int(bbox.get('width', 0))}px;
  height: {int(bbox.get('height', 0))}px;
  {bg}
}}
</style>
'''

        lines = [
            f"# Generated Code: {component_name}",
            f"**Framework:** {params.framework.value}",
            f"**Source Node:** `{params.node_id}`",
            "",
            "```" + ("tsx" if "react" in params.framework.value else "vue" if "vue" in params.framework.value else "html"),
            code,
            "```"
        ]

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_colors",
    annotations={
        "title": "Extract Colors from Figma",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_colors(params: FigmaColorsInput) -> str:
    """
    Extract all colors (fills, strokes, shadows) from a Figma file or node.

    Returns colors in both hex and rgba format for easy use in CSS/code.

    Args:
        params: FigmaColorsInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to analyze
            - include_fills: Include fill colors (default: True)
            - include_strokes: Include stroke colors (default: True)
            - include_shadows: Include shadow colors (default: True)

    Returns:
        str: JSON formatted color list with hex and rgba values
    """
    try:
        # Use full file endpoint to get children data
        data = await _make_figma_request(f"files/{params.file_key}")
        node = _get_node_with_children(params.file_key, params.node_id, data)

        if not node:
            return f"Error: Node '{params.node_id}' not found."

        result = {
            "fills": [],
            "strokes": [],
            "shadows": []
        }

        # Extract fills
        if params.include_fills:
            colors: List[Dict[str, Any]] = []
            _extract_colors_from_node(node, colors)
            fill_colors = [c for c in colors if c.get('type') == 'fill']
            # Convert to hex + rgba format
            for c in fill_colors:
                hex_val = c['value']
                # Parse hex to rgba
                if hex_val.startswith('rgba'):
                    rgba_val = hex_val
                elif hex_val.startswith('#'):
                    r = int(hex_val[1:3], 16)
                    g = int(hex_val[3:5], 16)
                    b = int(hex_val[5:7], 16)
                    rgba_val = f"rgba({r}, {g}, {b}, 1)"
                else:
                    rgba_val = hex_val
                result["fills"].append({
                    "name": c['name'],
                    "hex": hex_val if hex_val.startswith('#') else None,
                    "rgba": rgba_val
                })

        # Extract strokes
        if params.include_strokes:
            colors = []
            _extract_colors_from_node(node, colors)
            stroke_colors = [c for c in colors if c.get('type') == 'stroke']
            for c in stroke_colors:
                hex_val = c['value']
                if hex_val.startswith('rgba'):
                    rgba_val = hex_val
                elif hex_val.startswith('#'):
                    r = int(hex_val[1:3], 16)
                    g = int(hex_val[3:5], 16)
                    b = int(hex_val[5:7], 16)
                    rgba_val = f"rgba({r}, {g}, {b}, 1)"
                else:
                    rgba_val = hex_val
                result["strokes"].append({
                    "name": c['name'],
                    "hex": hex_val if hex_val.startswith('#') else None,
                    "rgba": rgba_val
                })

        # Extract shadows
        if params.include_shadows:
            shadows: List[Dict[str, Any]] = []
            _extract_shadows_from_node(node, shadows)
            result["shadows"] = shadows

        # Deduplicate by hex value
        for key in ["fills", "strokes"]:
            seen = set()
            unique = []
            for item in result[key]:
                hex_key = item.get('hex') or item.get('rgba')
                if hex_key not in seen:
                    seen.add(hex_key)
                    unique.append(item)
            result[key] = unique

        return json.dumps(result, indent=2)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_typography",
    annotations={
        "title": "Extract Typography from Figma",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_typography(params: FigmaTypographyInput) -> str:
    """
    Extract typography styles (font family, size, weight, line-height) from a Figma file.

    Analyzes all TEXT nodes and returns their typography properties.

    Args:
        params: FigmaTypographyInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to analyze

    Returns:
        str: JSON formatted typography list
    """
    try:
        data = await _make_figma_request(f"files/{params.file_key}")
        node = _get_node_with_children(params.file_key, params.node_id, data)

        if not node:
            return f"Error: Node '{params.node_id}' not found."

        typography: List[Dict[str, Any]] = []
        _extract_typography_from_node(node, typography)

        # Deduplicate by font properties
        seen = set()
        unique = []
        for t in typography:
            key = f"{t.get('fontFamily')}_{t.get('fontSize')}_{t.get('fontWeight')}"
            if key not in seen:
                seen.add(key)
                unique.append(t)

        result = {
            "typography": unique,
            "summary": {
                "fontFamilies": list(set(t.get('fontFamily', 'Unknown') for t in unique)),
                "fontSizes": sorted(set(t.get('fontSize', 16) for t in unique)),
                "fontWeights": sorted(set(t.get('fontWeight', 400) for t in unique))
            }
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="figma_get_spacing",
    annotations={
        "title": "Extract Spacing from Figma",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_spacing(params: FigmaSpacingInput) -> str:
    """
    Extract spacing values (padding, gap) from a Figma file.

    Analyzes auto-layout frames and returns their padding and gap values.

    Args:
        params: FigmaSpacingInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to analyze

    Returns:
        str: JSON formatted spacing list
    """
    try:
        data = await _make_figma_request(f"files/{params.file_key}")
        node = _get_node_with_children(params.file_key, params.node_id, data)

        if not node:
            return f"Error: Node '{params.node_id}' not found."

        spacing: List[Dict[str, Any]] = []
        _extract_spacing_from_node(node, spacing)

        # Filter to only auto-layout items
        auto_layout_items = [s for s in spacing if s.get('type') == 'auto-layout']

        # Deduplicate by padding/gap combination
        seen = set()
        unique = []
        for s in auto_layout_items:
            key = f"{s.get('paddingTop')}_{s.get('paddingRight')}_{s.get('paddingBottom')}_{s.get('paddingLeft')}_{s.get('itemSpacing')}"
            if key not in seen:
                seen.add(key)
                unique.append({
                    "name": s['name'],
                    "padding": {
                        "top": s.get('paddingTop', 0),
                        "right": s.get('paddingRight', 0),
                        "bottom": s.get('paddingBottom', 0),
                        "left": s.get('paddingLeft', 0)
                    },
                    "gap": s.get('itemSpacing', 0),
                    "layoutMode": s.get('layoutMode', 'NONE')
                })

        # Extract unique spacing values
        all_paddings = set()
        all_gaps = set()
        for s in unique:
            padding = s['padding']
            all_paddings.update([padding['top'], padding['right'], padding['bottom'], padding['left']])
            all_gaps.add(s['gap'])

        result = {
            "spacing": unique,
            "summary": {
                "uniquePaddingValues": sorted(all_paddings),
                "uniqueGapValues": sorted(all_gaps)
            }
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return _handle_api_error(e)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
