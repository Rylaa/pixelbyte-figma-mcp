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
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal, Annotated, Tuple, Callable
from enum import Enum
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict, BeforeValidator
from mcp.server.fastmcp import FastMCP

# Generator modules
from generators.react_generator import generate_react_code as _generate_react_code
from generators.vue_generator import generate_vue_code as _generate_vue_code
from generators.css_generator import generate_css_code as _generate_css_code, generate_scss_code as _generate_scss_code
from generators.kotlin_generator import generate_kotlin_code as _generate_kotlin_code
from generators.base import (
    sanitize_component_name as _sanitize_component_name,
    MAX_CHILDREN_LIMIT,
    MAX_NATIVE_CHILDREN_LIMIT,
)


# ============================================================================
# Reusable Validators (Annotated Types)
# ============================================================================

def _extract_file_key(v: str) -> str:
    """Extract Figma file key from URL or return as-is."""
    if 'figma.com' in v:
        match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
        if match:
            return match.group(1)
        raise ValueError("Could not extract file key from Figma URL")
    return v


def _normalize_node_id(v: str) -> str:
    """Convert node ID from 1-2 format to 1:2 format."""
    return v.replace('-', ':') if v else v


def _normalize_optional_node_id(v: Optional[str]) -> Optional[str]:
    """Convert optional node ID from 1-2 format to 1:2 format."""
    return v.replace('-', ':') if v else v


def _normalize_node_ids(v: List[str]) -> List[str]:
    """Convert list of node IDs from 1-2 format to 1:2 format."""
    return [nid.replace('-', ':') for nid in v]


# Annotated types for reuse across all models
FigmaFileKey = Annotated[str, BeforeValidator(_extract_file_key), Field(min_length=10, max_length=50)]
FigmaNodeId = Annotated[str, BeforeValidator(_normalize_node_id), Field(min_length=1)]
FigmaOptionalNodeId = Annotated[Optional[str], BeforeValidator(_normalize_optional_node_id)]
FigmaNodeIdList = Annotated[List[str], BeforeValidator(_normalize_node_ids)]

# ============================================================================
# Constants
# ============================================================================

FIGMA_API_BASE = "https://api.figma.com/v1"
CHARACTER_LIMIT = 80000
DEFAULT_TIMEOUT = 30.0

# Retry configuration for network errors
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # Base delay in seconds (exponential backoff)

# Tailwind CSS font weight mapping
TAILWIND_WEIGHT_MAP = {
    100: 'font-thin',
    200: 'font-extralight',
    300: 'font-light',
    400: 'font-normal',
    500: 'font-medium',
    600: 'font-semibold',
    700: 'font-bold',
    800: 'font-extrabold',
    900: 'font-black'
}

# SwiftUI font weight mapping
SWIFTUI_WEIGHT_MAP = {
    100: '.ultraLight',
    200: '.thin',
    300: '.light',
    400: '.regular',
    500: '.medium',
    600: '.semibold',
    700: '.bold',
    800: '.heavy',
    900: '.black'
}

# Kotlin Compose font weight mapping
KOTLIN_WEIGHT_MAP = {
    100: 'FontWeight.Thin',
    200: 'FontWeight.ExtraLight',
    300: 'FontWeight.Light',
    400: 'FontWeight.Normal',
    500: 'FontWeight.Medium',
    600: 'FontWeight.SemiBold',
    700: 'FontWeight.Bold',
    800: 'FontWeight.ExtraBold',
    900: 'FontWeight.Black'
}

# Tailwind text alignment mapping
TAILWIND_ALIGN_MAP = {
    'LEFT': 'text-left',
    'CENTER': 'text-center',
    'RIGHT': 'text-right',
    'JUSTIFIED': 'text-justify'
}


# ============================================================================
# Initialize MCP Server
# ============================================================================

SERVER_VERSION = "3.2.13"

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

    file_key: FigmaFileKey = Field(
        ...,
        description="Figma file key (from URL: figma.com/design/FILE_KEY/...)"
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
    include_empty_frames: bool = Field(
        default=False,
        description="Include frames/groups with no children (default: False to reduce noise)"
    )
    min_children_count: int = Field(
        default=0,
        description="Minimum number of children a frame must have to be included (0 = no minimum)",
        ge=0,
        le=100
    )
    mark_downloadable_assets: bool = Field(
        default=True,
        description="Mark nodes that contain downloadable assets (images, vectors, icons)"
    )


class FigmaNodeInput(BaseModel):
    """Input model for node operations."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaNodeId = Field(..., description="Node ID (e.g., '1:2' or '1-2')")
    framework: Optional[str] = Field(
        default=None,
        description="Target framework for implementation hints: 'css', 'swiftui', 'kotlin'. If not provided, defaults to 'css'."
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class FigmaScreenshotInput(BaseModel):
    """Input model for screenshot operations."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_ids: FigmaNodeIdList = Field(
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


class FigmaDesignTokensInput(BaseModel):
    """Input model for design token extraction."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaOptionalNodeId = Field(
        default=None,
        description="Optional node ID to extract tokens from specific component"
    )
    include_colors: bool = Field(default=True, description="Include color tokens")
    include_typography: bool = Field(default=True, description="Include typography tokens")
    include_spacing: bool = Field(default=True, description="Include spacing/padding tokens")
    include_effects: bool = Field(default=True, description="Include shadow/blur effects")
    include_generated_code: bool = Field(
        default=True,
        description="Include ready-to-use CSS variables, SCSS variables, and Tailwind config"
    )


class FigmaCodeGenInput(BaseModel):
    """Input model for code generation."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaNodeId = Field(..., description="Node ID to generate code for")
    framework: CodeFramework = Field(
        default=CodeFramework.REACT_TAILWIND,
        description="Target framework"
    )
    component_name: Optional[str] = Field(
        default=None,
        description="Component name (auto-generated from node name if not provided)"
    )


class FigmaStylesInput(BaseModel):
    """Input model for published styles retrieval."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    include_fill_styles: bool = Field(default=True, description="Include fill/color styles")
    include_text_styles: bool = Field(default=True, description="Include text/typography styles")
    include_effect_styles: bool = Field(default=True, description="Include effect styles (shadows, blurs)")
    include_grid_styles: bool = Field(default=True, description="Include grid/layout styles")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


# ============================================================================
# Code Connect Input Models
# ============================================================================

class CodeConnectMapping(BaseModel):
    """Code Connect mapping data model."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    component_path: str = Field(..., description="Path to the code component file")
    component_name: str = Field(..., description="Name of the code component")
    props_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of Figma property names to code prop names"
    )
    variants: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Variant mappings with their prop values"
    )
    example: Optional[str] = Field(
        default=None,
        description="Example usage code snippet"
    )
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class FigmaCodeConnectGetInput(BaseModel):
    """Input model for getting Code Connect mappings."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaOptionalNodeId = Field(
        default=None,
        description="Optional node ID to get specific mapping (returns all if not provided)"
    )


class FigmaCodeConnectAddInput(BaseModel):
    """Input model for adding Code Connect mapping."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaNodeId = Field(..., description="Figma node ID to map")
    component_path: str = Field(
        ...,
        description="Path to the code component (e.g., 'src/components/Button.tsx')",
        min_length=1
    )
    component_name: str = Field(
        ...,
        description="Name of the code component (e.g., 'Button')",
        min_length=1
    )
    props_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of Figma property names to code prop names (e.g., {'Variant': 'variant'})"
    )
    variants: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Variant mappings (e.g., {'primary': {'variant': 'primary'}})"
    )
    example: Optional[str] = Field(
        default=None,
        description="Example usage code snippet"
    )


class FigmaCodeConnectRemoveInput(BaseModel):
    """Input model for removing Code Connect mapping."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaNodeId = Field(..., description="Figma node ID to remove mapping for")


class FigmaListAssetsInput(BaseModel):
    """Input model for listing assets in a Figma file/node."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaOptionalNodeId = Field(
        default=None,
        description="Optional node ID to search within (searches entire file if not provided)"
    )
    include_images: bool = Field(
        default=True,
        description="Include image fills in results"
    )
    include_icons: bool = Field(
        default=True,
        description="Include detected icon frames (smart detection by name pattern and size)"
    )
    include_vectors: bool = Field(
        default=False,
        description="Include raw vector nodes (individual paths). Usually not needed when include_icons=True"
    )
    include_exports: bool = Field(
        default=True,
        description="Include nodes with export settings"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class FigmaGetImagesInput(BaseModel):
    """Input model for getting image fill URLs."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_id: FigmaOptionalNodeId = Field(
        default=None,
        description="Optional node ID to get images from"
    )


class FigmaExportAssetsInput(BaseModel):
    """Input model for batch asset export."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: FigmaFileKey = Field(..., description="Figma file key")
    node_ids: FigmaNodeIdList = Field(
        ...,
        description="List of node IDs to export",
        min_length=1,
        max_length=50
    )
    format: ImageFormat = Field(
        default=ImageFormat.PNG,
        description="Export format: png, svg, jpg, pdf"
    )
    scale: float = Field(
        default=2.0,
        description="Scale factor (0.01 to 4.0)",
        ge=0.01,
        le=4.0
    )
    include_svg_for_vectors: bool = Field(
        default=True,
        description="Generate inline SVG for vector nodes"
    )


# ============================================================================
# Helper Functions
# ============================================================================

# Code Connect storage configuration
CODE_CONNECT_DEFAULT_PATH = os.path.expanduser(
    "~/.config/pixelbyte-figma-mcp/code_connect.json"
)


def _get_code_connect_path() -> str:
    """Get the path to the Code Connect storage file."""
    return os.environ.get("FIGMA_CODE_CONNECT_PATH", CODE_CONNECT_DEFAULT_PATH)


def _load_code_connect_data() -> Dict[str, Any]:
    """Load Code Connect mappings from storage file."""
    path = _get_code_connect_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"version": "1.0", "mappings": {}}
    return {"version": "1.0", "mappings": {}}


def _save_code_connect_data(data: Dict[str, Any]) -> None:
    """Save Code Connect mappings to storage file."""
    path = _get_code_connect_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


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
    """Make authenticated request to Figma API with retry logic."""
    token = _get_figma_token()
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
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
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise
        except httpx.HTTPStatusError:
            raise

    raise last_exception


def _with_version(response: str) -> str:
    """Append server version footer to tool responses."""
    return f"{response}\n\n---\n_MCP Server v{SERVER_VERSION}_"


def _versioned_tool(*args, **kwargs):
    """Decorator that wraps mcp.tool() and appends server version to responses."""
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def wrapper(*fn_args, **fn_kwargs):
            result = await func(*fn_args, **fn_kwargs)
            if isinstance(result, str):
                return _with_version(result)
            return result

        return mcp.tool(*args, **kwargs)(wrapper)
    return decorator


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
    elif isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "Error: Could not connect to Figma API after multiple retries. Check your internet connection."
    elif isinstance(e, OSError) and "nodename nor servname" in str(e):
        return "Error: DNS resolution failed for Figma API. Check your internet connection and try again."
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


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple (0-255 values)."""
    # Handle rgba format
    if hex_color.startswith('rgba'):
        import re
        match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+)', hex_color)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (0, 0, 0)

    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 0, 0)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple:
    """Convert RGB (0-255) to HSL (h: 0-360, s: 0-100, l: 0-100)."""
    r, g, b = r / 255, g / 255, b / 255
    max_c, min_c = max(r, g, b), min(r, g, b)
    l = (max_c + min_c) / 2

    if max_c == min_c:
        h = s = 0
    else:
        d = max_c - min_c
        s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
        if max_c == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif max_c == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6

    return (round(h * 360), round(s * 100), round(l * 100))


def _calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance for WCAG contrast ratio (0-255 RGB values)."""
    def adjust(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
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

    import math
    angle = math.degrees(math.atan2(dy, dx))
    # Convert to CSS gradient angle (0deg = up, clockwise)
    css_angle = 90 - angle
    return round(css_angle, 2)


def _extract_gradient_stops(gradient_stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract gradient color stops."""
    stops = []
    for stop in gradient_stops:
        color = stop.get('color', {})
        stops.append({
            'position': round(stop.get('position', 0), 4),
            'color': _rgba_to_hex(color),
            'opacity': color.get('a', 1)
        })
    return stops


def _extract_fill_data(fill: Dict[str, Any], node_name: str) -> Optional[Dict[str, Any]]:
    """Extract comprehensive fill data including gradients and images."""
    if not fill.get('visible', True):
        return None

    fill_type = fill.get('type', 'SOLID')

    base_data = {
        'name': node_name,
        'category': 'fill',
        'fillType': fill_type,
        'opacity': fill.get('opacity', 1),
        'blendMode': fill.get('blendMode', 'NORMAL')
    }

    if fill_type == 'SOLID':
        color = fill.get('color', {})
        hex_color = _rgba_to_hex(color)
        base_data['hex'] = hex_color

        # Add rich color information for solid colors
        rgb = _hex_to_rgb(hex_color)
        hsl = _rgb_to_hsl(*rgb)
        base_data['rgb'] = f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
        base_data['hsl'] = f"{hsl[0]}, {hsl[1]}%, {hsl[2]}%"
        base_data['contrast'] = {
            'white': _contrast_ratio(rgb, (255, 255, 255)),
            'black': _contrast_ratio(rgb, (0, 0, 0))
        }
        # Keep 'color' for backward compatibility
        base_data['color'] = hex_color

    elif fill_type in ['GRADIENT_LINEAR', 'GRADIENT_RADIAL', 'GRADIENT_ANGULAR', 'GRADIENT_DIAMOND']:
        gradient_stops = fill.get('gradientStops', [])
        handle_positions = fill.get('gradientHandlePositions', [])

        base_data['gradient'] = {
            'type': fill_type.replace('GRADIENT_', ''),
            'stops': _extract_gradient_stops(gradient_stops),
            'handlePositions': handle_positions
        }

        if fill_type == 'GRADIENT_LINEAR':
            base_data['gradient']['angle'] = _calculate_gradient_angle(handle_positions)

    elif fill_type == 'IMAGE':
        base_data['image'] = {
            'imageRef': fill.get('imageRef'),
            'scaleMode': fill.get('scaleMode', 'FILL'),
            'imageTransform': fill.get('imageTransform'),
            'scalingFactor': fill.get('scalingFactor'),
            'rotation': fill.get('rotation', 0),
            'filters': fill.get('filters', {})
        }

    return base_data


def _extract_stroke_data(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract comprehensive stroke data."""
    strokes = node.get('strokes', [])
    if not strokes:
        return None

    stroke_colors = []
    for stroke in strokes:
        if stroke.get('visible', True):
            stroke_type = stroke.get('type', 'SOLID')
            stroke_data = {
                'type': stroke_type,
                'opacity': stroke.get('opacity', 1),
                'blendMode': stroke.get('blendMode', 'NORMAL')
            }

            if stroke_type == 'SOLID':
                hex_color = _rgba_to_hex(stroke.get('color', {}))
                stroke_data['hex'] = hex_color
                stroke_data['color'] = hex_color
                # Add rich color information
                rgb = _hex_to_rgb(hex_color)
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


def _extract_corner_radii(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract individual corner radii."""
    # Check for individual corner radii first
    if 'rectangleCornerRadii' in node:
        radii = node['rectangleCornerRadii']
        return {
            'topLeft': radii[0] if len(radii) > 0 else 0,
            'topRight': radii[1] if len(radii) > 1 else 0,
            'bottomRight': radii[2] if len(radii) > 2 else 0,
            'bottomLeft': radii[3] if len(radii) > 3 else 0,
            'isUniform': len(set(radii)) == 1
        }

    # Fall back to single cornerRadius
    corner_radius = node.get('cornerRadius', 0)
    if corner_radius:
        return {
            'topLeft': corner_radius,
            'topRight': corner_radius,
            'bottomRight': corner_radius,
            'bottomLeft': corner_radius,
            'isUniform': True
        }

    return None


def _extract_children_summary(children: List[Dict[str, Any]], depth: int = 0, max_depth: int = 2) -> List[Dict[str, Any]]:
    """Extract summary information for child nodes up to max_depth.

    Depth 0 (direct children): name, type, id, size, fills summary, text content, child count
    Depth 1 (grandchildren): name, type, id, size, child count
    """
    MAX_CHILDREN_PER_LEVEL = 30
    summaries = []

    for child in children[:MAX_CHILDREN_PER_LEVEL]:
        if not child.get('visible', True):
            continue

        summary: Dict[str, Any] = {
            'name': child.get('name', 'Unknown'),
            'type': child.get('type', 'UNKNOWN'),
            'id': child.get('id', ''),
        }

        # Size from bounding box
        bbox = child.get('absoluteBoundingBox')
        if bbox:
            summary['width'] = round(bbox.get('width', 0), 1)
            summary['height'] = round(bbox.get('height', 0), 1)

        # Depth 0 gets richer details
        if depth == 0:
            # Fills summary (compact)
            fills = child.get('fills', [])
            visible_fills = [f for f in fills if f.get('visible', True)]
            if visible_fills:
                fill_summary = []
                for f in visible_fills[:3]:
                    f_type = f.get('type', '')
                    if f_type == 'SOLID':
                        color = f.get('color', {})
                        hex_color = '#{:02x}{:02x}{:02x}'.format(
                            int(color.get('r', 0) * 255),
                            int(color.get('g', 0) * 255),
                            int(color.get('b', 0) * 255)
                        )
                        fill_summary.append(hex_color)
                    elif 'GRADIENT' in f_type:
                        fill_summary.append(f_type.replace('GRADIENT_', '').lower() + ' gradient')
                    elif f_type == 'IMAGE':
                        fill_summary.append('image')
                if fill_summary:
                    summary['fills'] = fill_summary

            # Text content
            if child.get('type') == 'TEXT':
                chars = child.get('characters', '')
                if chars:
                    summary['text'] = chars[:100] + ('...' if len(chars) > 100 else '')

            # Auto-layout info
            layout_mode = child.get('layoutMode')
            if layout_mode and layout_mode != 'NONE':
                summary['layoutMode'] = layout_mode
                gap = child.get('itemSpacing', 0)
                if gap:
                    summary['gap'] = gap

        # Recurse into grandchildren
        grandchildren = child.get('children', [])
        if grandchildren:
            summary['childrenCount'] = len(grandchildren)
            if depth < max_depth - 1:
                summary['children'] = _extract_children_summary(grandchildren, depth + 1, max_depth)

        summaries.append(summary)

    if len(children) > MAX_CHILDREN_PER_LEVEL:
        summaries.append({
            '_truncated': True,
            '_message': f'{len(children) - MAX_CHILDREN_PER_LEVEL} more children not shown.'
        })

    return summaries


def _render_children_markdown(lines: List[str], children: List[Dict[str, Any]], indent: int = 0) -> None:
    """Render children summary list as markdown."""
    prefix = '  ' * indent
    for child in children:
        if child.get('_truncated'):
            lines.append(f"{prefix}- _{child.get('_message', 'truncated')}_")
            continue

        name = child.get('name', 'Unknown')
        node_type = child.get('type', '')
        node_id = child.get('id', '')
        w = child.get('width', 0)
        h = child.get('height', 0)

        # Main line: name, type, size
        size_str = f" ({w}x{h})" if w or h else ""
        line = f"{prefix}- **{name}** `{node_type}` `{node_id}`{size_str}"
        lines.append(line)

        # Fills (depth-0 only)
        fills = child.get('fills')
        if fills:
            lines.append(f"{prefix}  - Fills: {', '.join(str(f) for f in fills)}")

        # Text content
        text = child.get('text')
        if text:
            lines.append(f'{prefix}  - Text: "{text}"')

        # Layout
        layout = child.get('layoutMode')
        if layout:
            gap = child.get('gap', 0)
            gap_str = f", gap: {gap}" if gap else ""
            lines.append(f"{prefix}  - Layout: {layout}{gap_str}")

        # Recurse into grandchildren
        sub_children = child.get('children')
        if sub_children:
            _render_children_markdown(lines, sub_children, indent + 1)
        elif child.get('childrenCount', 0) > 0:
            lines.append(f"{prefix}  - Children: {child['childrenCount']} node(s)")

    lines.append("")


def _extract_constraints(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract layout constraints for responsive behavior."""
    constraints = node.get('constraints', {})
    if not constraints:
        return None

    return {
        'horizontal': constraints.get('horizontal', 'LEFT'),
        'vertical': constraints.get('vertical', 'TOP')
    }


def _extract_transform(node: Dict[str, Any]) -> Dict[str, Any]:
    """Extract transform properties including flip detection."""
    transform = {
        'rotation': node.get('rotation', 0),
        'preserveRatio': node.get('preserveRatio', False)
    }

    if 'relativeTransform' in node:
        transform['relativeTransform'] = node['relativeTransform']
        # Detect flip from negative scale in transform matrix
        # relativeTransform: [[a, b, tx], [c, d, ty]]
        rt = node['relativeTransform']
        try:
            a = float(rt[0][0])
            d = float(rt[1][1])
            if a < 0:
                transform['flippedHorizontally'] = True
            if d < 0:
                transform['flippedVertically'] = True
        except (IndexError, TypeError, ValueError):
            pass

    return transform


def _extract_component_info(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract component/instance information with full variant details."""
    node_type = node.get('type', '')

    if node_type == 'INSTANCE':
        result = {
            'isInstance': True,
            'componentId': node.get('componentId'),
            'componentProperties': node.get('componentProperties', {}),
            'overrides': node.get('overrides', []),
            'exposedInstances': node.get('exposedInstances', [])
        }

        # Add variant properties if this is a variant instance
        variant_props = node.get('variantProperties')
        if variant_props:
            result['variantProperties'] = variant_props

        # Add main component info if available (for tracking source component)
        main_component = node.get('mainComponent')
        if main_component and isinstance(main_component, dict):
            result['mainComponent'] = {
                'id': main_component.get('id'),
                'name': main_component.get('name'),
                'componentSetId': main_component.get('componentSetId')
            }

        # Add component set name for variant context
        if node.get('componentSetName'):
            result['componentSetName'] = node.get('componentSetName')

        return result

    elif node_type == 'COMPONENT':
        result = {
            'isComponent': True,
            'componentPropertyDefinitions': node.get('componentPropertyDefinitions', {}),
            'componentSetId': node.get('componentSetId')
        }

        # Add variant properties if this component is a variant
        variant_props = node.get('variantProperties')
        if variant_props:
            result['variantProperties'] = variant_props

        return result

    elif node_type == 'COMPONENT_SET':
        return {
            'isComponentSet': True,
            'componentPropertyDefinitions': node.get('componentPropertyDefinitions', {}),
            'variantGroupProperties': node.get('variantGroupProperties', {})
        }

    return None


def _extract_bound_variables(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract Figma variables bound to this node."""
    bound_variables = node.get('boundVariables', {})
    if not bound_variables:
        return None

    extracted = {}
    for prop, binding in bound_variables.items():
        if isinstance(binding, dict):
            extracted[prop] = {
                'variableId': binding.get('id'),
                'type': binding.get('type')
            }
        elif isinstance(binding, list):
            # For properties that can have multiple bindings (like fills)
            extracted[prop] = [
                {'variableId': b.get('id'), 'type': b.get('type')}
                for b in binding if isinstance(b, dict)
            ]

    return extracted if extracted else None


def _extract_mask_data(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract mask information from a node.

    Returns mask configuration if the node is a mask.
    """
    if not node.get('isMask'):
        return None

    return {
        'isMask': True,
        'maskType': node.get('maskType', 'ALPHA'),  # ALPHA, VECTOR, LUMINANCE
        'clipsContent': node.get('clipsContent', False)
    }


def _extract_image_references(node: Dict[str, Any], file_key: str = '') -> Optional[List[Dict[str, Any]]]:
    """Extract image references from node fills.

    Returns image reference information that can be resolved to actual URLs
    using the Figma /images endpoint.
    """
    fills = node.get('fills', [])
    if not fills:
        return None

    images = []
    for fill in fills:
        if fill.get('type') == 'IMAGE' and fill.get('visible', True):
            image_ref = fill.get('imageRef')
            if image_ref:
                image_info = {
                    'imageRef': image_ref,
                    'scaleMode': fill.get('scaleMode', 'FILL'),  # FILL, FIT, TILE, STRETCH
                    'opacity': fill.get('opacity', 1),
                }

                # Image transform for rotation/scale
                if fill.get('imageTransform'):
                    image_info['imageTransform'] = fill.get('imageTransform')

                # Scaling factor
                if fill.get('scalingFactor'):
                    image_info['scalingFactor'] = fill.get('scalingFactor')

                # Rotation
                if fill.get('rotation'):
                    image_info['rotation'] = fill.get('rotation')

                # Filters (exposure, contrast, saturation, etc.)
                filters = fill.get('filters', {})
                if filters:
                    image_info['filters'] = filters

                # URL hint for fetching via Figma API
                if file_key:
                    image_info['apiUrlHint'] = f"/v1/files/{file_key}/images"

                images.append(image_info)

    return images if images else None


async def _resolve_image_urls(file_key: str, image_refs: List[str]) -> Dict[str, str]:
    """Resolve Figma image references to actual downloadable URLs.

    Uses the Figma /images endpoint to convert internal imageRef values
    to real S3 URLs that can be downloaded (valid for 30 days).

    Args:
        file_key: Figma file key
        image_refs: List of imageRef values to resolve

    Returns:
        Dict mapping imageRef to actual URL
    """
    if not image_refs:
        return {}

    try:
        # Use the /images endpoint with image refs
        data = await _make_figma_request(
            f"files/{file_key}/images"
        )

        # The response contains a mapping of imageRef -> URL
        images = data.get('meta', {}).get('images', {})
        return images
    except Exception:
        return {}


def _generate_svg_from_paths(vector_paths: Dict[str, Any], node: Dict[str, Any]) -> Optional[str]:
    """Generate SVG markup from vector path geometry.

    Creates a complete SVG element from fillGeometry and strokeGeometry data.

    Args:
        vector_paths: Vector path data from _extract_vector_paths()
        node: The node dict containing fill/stroke colors and bounds

    Returns:
        Complete SVG string or None if no valid paths
    """
    fill_geometry = vector_paths.get('fillGeometry', [])
    stroke_geometry = vector_paths.get('strokeGeometry', [])

    if not fill_geometry and not stroke_geometry:
        return None

    # Get bounding box for viewBox
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 24)
    height = bbox.get('height', 24)

    # Get fill color
    fill_color = '#000000'
    fills = node.get('fills', [])
    for fill in fills:
        if fill.get('type') == 'SOLID' and fill.get('visible', True):
            color = fill.get('color', {})
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            fill_color = f'#{r:02x}{g:02x}{b:02x}'
            break

    # Get stroke color
    stroke_color = 'none'
    stroke_width = 0
    strokes = node.get('strokes', [])
    for stroke in strokes:
        if stroke.get('type') == 'SOLID' and stroke.get('visible', True):
            color = stroke.get('color', {})
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            stroke_color = f'#{r:02x}{g:02x}{b:02x}'
            stroke_width = node.get('strokeWeight', 1)
            break

    # Build SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}">'
    ]

    # Add fill paths
    for geom in fill_geometry:
        path_data = geom.get('path', '')
        if path_data:
            svg_parts.append(f'  <path d="{path_data}" fill="{fill_color}" />')

    # Add stroke paths
    for geom in stroke_geometry:
        path_data = geom.get('path', '')
        if path_data:
            svg_parts.append(f'  <path d="{path_data}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" />')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def _is_icon_frame(node: Dict[str, Any]) -> bool:
    """Detect if a node is likely an icon frame.

    Uses smart heuristics to identify icon frames:
    1. Name pattern: Contains ':' (icon library pattern like 'mynaui:image-solid')
    2. Size: Reasonable icon size (8-128px, roughly square)
    3. Structure: Has vector children (actual icon content)

    Args:
        node: The node to check

    Returns:
        True if the node appears to be an icon frame
    """
    node_name = node.get('name', '')
    node_type = node.get('type', '')

    # Must be a frame or group type
    if node_type not in ['FRAME', 'GROUP', 'COMPONENT', 'INSTANCE']:
        return False

    # Check for icon library naming pattern (contains ':')
    has_icon_pattern = ':' in node_name

    # Check size - icons are typically 8-128px and roughly square
    abs_box = node.get('absoluteBoundingBox', {})
    width = abs_box.get('width', 0)
    height = abs_box.get('height', 0)

    is_icon_size = False
    if width > 0 and height > 0:
        min_dim = min(width, height)
        max_dim = max(width, height)
        # Icon size range (8-128px) and aspect ratio close to 1:1 (allow up to 1.5:1)
        is_icon_size = 8 <= min_dim <= 128 and max_dim / min_dim <= 1.5

    # Check if has vector children (actual icon content)
    vector_types = {'VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'POLYGON', 'ELLIPSE', 'LINE', 'REGULAR_POLYGON'}
    has_vector_children = False
    for child in node.get('children', []):
        if child.get('type') in vector_types:
            has_vector_children = True
            break
        # Also check nested children (for grouped icons)
        for grandchild in child.get('children', []):
            if grandchild.get('type') in vector_types:
                has_vector_children = True
                break

    # Icon detection logic:
    # - If has icon library naming pattern → likely icon
    # - If icon-sized frame with vector children → likely icon
    return has_icon_pattern or (is_icon_size and has_vector_children)


def _is_chart_or_illustration(node: Dict[str, Any]) -> bool:
    """Detect if a node is likely a chart or illustration (not an icon).

    Uses heuristics to identify charts/illustrations:
    1. Has exportSettings configured AND larger than typical icon size
    2. Large frame with multiple vector children (complex structure)

    Args:
        node: The node to check

    Returns:
        True if the node appears to be a chart or illustration
    """
    # Check size - charts are typically larger than icons
    abs_box = node.get('absoluteBoundingBox', {})
    width = abs_box.get('width', 0)
    height = abs_box.get('height', 0)

    # Icon size threshold - icons are typically <= 64px
    is_icon_sized = width <= 64 and height <= 64
    is_large = width > 50 or height > 50

    # If has exportSettings AND is larger than icon size, it's likely a chart/illustration
    # Small icons can also have exportSettings, so we check size first
    if node.get('exportSettings') and not is_icon_sized:
        return True

    # Count children - charts typically have multiple elements
    children = node.get('children', [])
    child_count = len(children)

    # Count vector children
    vector_types = {'VECTOR', 'RECTANGLE', 'ELLIPSE', 'LINE', 'BOOLEAN_OPERATION'}
    vector_count = sum(1 for c in children if c.get('type') in vector_types)

    # Chart heuristic: large frame with multiple vector children
    if is_large and child_count >= 3 and vector_count >= 2:
        return True

    return False


def _collect_all_assets(
    node: Dict[str, Any],
    file_key: str,
    assets: Dict[str, List],
    include_icons: bool = True,
    include_vectors: bool = False,
    include_exports: bool = True  # NEW: Add parameter
) -> None:
    """Recursively collect all assets from a node tree with smart icon detection.

    Finds image fills, icon frames, raw vectors, and nodes with export settings.
    When an icon frame is detected, it's added to the icons list and children
    are NOT traversed (avoiding duplicate vector entries).

    Args:
        node: The node to process
        file_key: Figma file key
        assets: Dict to accumulate assets into (modified in place)
        include_icons: Whether to detect and collect icon frames
        include_vectors: Whether to collect raw vector nodes
        include_exports: Whether to collect nodes with export settings
    """
    node_id = node.get('id', '')
    node_name = node.get('name', 'Unnamed')
    node_type = node.get('type', '')

    # Check for image fills
    image_refs = _extract_image_references(node, file_key)
    if image_refs:
        for img in image_refs:
            assets['images'].append({
                'nodeId': node_id,
                'nodeName': node_name,
                'imageRef': img.get('imageRef'),
                'scaleMode': img.get('scaleMode'),
                'filters': img.get('filters')
            })

    # FIX: Check for export settings FIRST (before icon detection)
    # This ensures nodes with exportSettings are always collected
    export_settings = _extract_export_settings(node)
    has_export_settings = bool(export_settings)

    if include_exports and has_export_settings:
        assets['exports'].append({
            'nodeId': node_id,
            'nodeName': node_name,
            'settings': export_settings
        })

    # Smart icon detection - if this is an icon frame, add it and DON'T recurse
    # FIX: Skip icon classification if node is a chart/illustration
    is_chart = _is_chart_or_illustration(node)

    if include_icons and not is_chart and _is_icon_frame(node):
        abs_box = node.get('absoluteBoundingBox', {})
        assets['icons'].append({
            'nodeId': node_id,
            'nodeName': node_name,
            'nodeType': node_type,
            'width': abs_box.get('width', 0),
            'height': abs_box.get('height', 0)
        })
        # Don't recurse into icon children - we treat the icon as a single asset
        return

    # Check for vector paths (SVG exportable) - only if include_vectors is True
    if include_vectors:
        vector_paths = _extract_vector_paths(node)
        if vector_paths:
            assets['vectors'].append({
                'nodeId': node_id,
                'nodeName': node_name,
                'nodeType': node_type,
                'hasPath': bool(vector_paths.get('fillGeometry') or vector_paths.get('strokeGeometry'))
            })

    # Recurse into children
    for child in node.get('children', []):
        _collect_all_assets(child, file_key, assets, include_icons, include_vectors, include_exports)


def _extract_vector_paths(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract vector path data for SVG export.

    Returns path geometry for vector nodes that can be used to generate SVG.
    """
    vector_types = ['VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'POLYGON', 'ELLIPSE', 'LINE', 'REGULAR_POLYGON']
    if node.get('type') not in vector_types:
        return None

    result = {}

    # Fill geometry (SVG path data for fills)
    fill_geometry = node.get('fillGeometry', [])
    if fill_geometry:
        result['fillGeometry'] = fill_geometry

    # Stroke geometry (SVG path data for strokes)
    stroke_geometry = node.get('strokeGeometry', [])
    if stroke_geometry:
        result['strokeGeometry'] = stroke_geometry

    # Vector network (vertices and segments for complex paths)
    vector_network = node.get('vectorNetwork')
    if vector_network:
        result['vectorNetwork'] = {
            'vertices': vector_network.get('vertices', []),
            'segments': vector_network.get('segments', []),
            'regions': vector_network.get('regions', [])
        }

    # Boolean operation type for BOOLEAN_OPERATION nodes
    if node.get('type') == 'BOOLEAN_OPERATION':
        result['booleanOperation'] = node.get('booleanOperation')  # UNION, INTERSECT, SUBTRACT, EXCLUDE

    # Star-specific properties
    if node.get('type') == 'STAR':
        result['starInnerRadius'] = node.get('starInnerRadius')

    # Polygon count
    if node.get('type') in ['STAR', 'POLYGON', 'REGULAR_POLYGON']:
        result['pointCount'] = node.get('pointCount')

    # Arc data for ellipses
    if node.get('type') == 'ELLIPSE':
        arc_data = node.get('arcData')
        if arc_data:
            result['arcData'] = arc_data

    return result if result else None


def _extract_interactions(node: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Extract prototype interactions for hover/click states.

    Returns interaction configurations including triggers and actions.
    Useful for AI to understand hover, click, and other interactive behaviors.
    """
    interactions = node.get('interactions', [])
    if not interactions:
        return None

    extracted = []
    for i in interactions:
        trigger = i.get('trigger', {})
        action = i.get('action', {})

        interaction = {
            'trigger': {
                'type': trigger.get('type'),  # ON_CLICK, ON_HOVER, ON_PRESS, ON_DRAG, AFTER_TIMEOUT, MOUSE_ENTER, MOUSE_LEAVE, MOUSE_UP, MOUSE_DOWN
            }
        }

        # Add timeout for AFTER_TIMEOUT trigger
        if trigger.get('type') == 'AFTER_TIMEOUT':
            interaction['trigger']['timeout'] = trigger.get('timeout')

        # Add delay if specified
        if trigger.get('delay'):
            interaction['trigger']['delay'] = trigger.get('delay')

        # Action details
        interaction['action'] = {
            'type': action.get('type'),  # NAVIGATE, OVERLAY, SCROLL_TO, URL, BACK, CLOSE, OPEN_URL, SET_VARIABLE
        }

        # Destination node for navigation actions
        if action.get('destinationId'):
            interaction['action']['destinationId'] = action.get('destinationId')

        # Navigation type
        if action.get('navigation'):
            interaction['action']['navigation'] = action.get('navigation')  # NAVIGATE, SWAP, OVERLAY, SCROLL_TO, SWAP_OVERLAY

        # URL for OPEN_URL action
        if action.get('url'):
            interaction['action']['url'] = action.get('url')

        # Transition configuration
        transition = action.get('transition', {})
        if transition:
            interaction['action']['transition'] = {
                'type': transition.get('type'),  # INSTANT, DISSOLVE, SMART_ANIMATE, MOVE_IN, MOVE_OUT, PUSH, SLIDE_IN, SLIDE_OUT
                'duration': transition.get('duration'),  # milliseconds
                'easing': transition.get('easing', {}).get('type') if isinstance(transition.get('easing'), dict) else transition.get('easing')
            }

        # Overlay positioning for overlay actions
        if action.get('overlayRelativePosition'):
            interaction['action']['overlayPosition'] = action.get('overlayRelativePosition')

        extracted.append(interaction)

    return extracted if extracted else None


def _extract_export_settings(node: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Extract export settings from a node.

    Returns export configurations including format, scale, and SVG options.
    """
    settings = node.get('exportSettings', [])
    if not settings:
        return None

    extracted = []
    for s in settings:
        export_config = {
            'format': s.get('format'),  # PNG, SVG, JPG, PDF
            'suffix': s.get('suffix', ''),
        }

        # Constraint (scale, width, height)
        constraint = s.get('constraint', {})
        if constraint:
            export_config['constraint'] = {
                'type': constraint.get('type'),  # SCALE, WIDTH, HEIGHT
                'value': constraint.get('value')
            }

        # SVG-specific options
        if s.get('format') == 'SVG':
            export_config['svgOptions'] = {
                'includeId': s.get('svgIncludeId', False),
                'simplifyStroke': s.get('svgSimplifyStroke', False),
                'outlineText': s.get('svgOutlineText', False)
            }

        # Image-specific options
        if s.get('format') in ('PNG', 'JPG'):
            if s.get('contentsOnly') is not None:
                export_config['contentsOnly'] = s.get('contentsOnly')
            if s.get('useAbsoluteBounds') is not None:
                export_config['useAbsoluteBounds'] = s.get('useAbsoluteBounds')

        extracted.append(export_config)

    return extracted if extracted else None


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
            hex_color = _rgba_to_hex(color)
            rgb = _hex_to_rgb(hex_color)
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


def _extract_auto_layout(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract comprehensive auto-layout properties."""
    layout_mode = node.get('layoutMode')
    if not layout_mode or layout_mode == 'NONE':
        return None

    return {
        'mode': layout_mode,
        'padding': {
            'top': node.get('paddingTop', 0),
            'right': node.get('paddingRight', 0),
            'bottom': node.get('paddingBottom', 0),
            'left': node.get('paddingLeft', 0)
        },
        'gap': node.get('itemSpacing', 0),
        'primaryAxisAlign': node.get('primaryAxisAlignItems', 'MIN'),
        'counterAxisAlign': node.get('counterAxisAlignItems', 'MIN'),
        'primaryAxisSizing': node.get('primaryAxisSizingMode', 'AUTO'),
        'counterAxisSizing': node.get('counterAxisSizingMode', 'AUTO'),
        'layoutWrap': node.get('layoutWrap', 'NO_WRAP'),
        'itemReverseZIndex': node.get('itemReverseZIndex', False),
        'strokesIncludedInLayout': node.get('strokesIncludedInLayout', False)
    }


def _extract_size_constraints(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract min/max size constraints."""
    constraints = {}

    if 'minWidth' in node:
        constraints['minWidth'] = node['minWidth']
    if 'maxWidth' in node:
        constraints['maxWidth'] = node['maxWidth']
    if 'minHeight' in node:
        constraints['minHeight'] = node['minHeight']
    if 'maxHeight' in node:
        constraints['maxHeight'] = node['maxHeight']

    return constraints if constraints else None


def _generate_implementation_hints(node: Dict[str, Any], interactions: Optional[List] = None, framework: str = 'css') -> Dict[str, Any]:
    """Generate AI-friendly implementation hints based on node analysis.

    Provides guidance for layout, responsiveness, interactions, accessibility,
    and component usage.
    """
    hints: Dict[str, Any] = {}
    layout_hints = []
    responsive_hints = []
    interaction_hints = []
    accessibility_hints = []
    component_hints = []

    node_type = node.get('type', '')
    node_name = node.get('name', '')
    layout_mode = node.get('layoutMode')

    # Layout hints
    spacing = node.get('itemSpacing', 0)
    if layout_mode:
        if framework in ('swiftui',):
            if layout_mode == 'VERTICAL':
                layout_hints.append(f"Use VStack with spacing: {spacing}")
            elif layout_mode == 'HORIZONTAL':
                layout_hints.append(f"Use HStack with spacing: {spacing}")

            # Check for wrapping
            if node.get('layoutWrap') == 'WRAP':
                layout_hints.append("Use LazyVGrid or custom flow layout for wrapping")

            # Alignment
            primary_align = node.get('primaryAxisAlignItems', 'MIN')
            counter_align = node.get('counterAxisAlignItems', 'MIN')
            if primary_align == 'SPACE_BETWEEN':
                layout_hints.append("Use Spacer() between items for distributed spacing")
            elif primary_align == 'CENTER':
                layout_hints.append("Center items along main axis with alignment: .center")
            if counter_align == 'CENTER':
                layout_hints.append("Center items along cross axis with alignment: .center")

        elif framework in ('kotlin',):
            if layout_mode == 'VERTICAL':
                layout_hints.append(f"Use Column with verticalArrangement spacedBy {spacing}.dp")
            elif layout_mode == 'HORIZONTAL':
                layout_hints.append(f"Use Row with horizontalArrangement spacedBy {spacing}.dp")

            # Check for wrapping
            if node.get('layoutWrap') == 'WRAP':
                layout_hints.append("Use FlowRow or FlowColumn for wrapping layout")

            # Alignment
            primary_align = node.get('primaryAxisAlignItems', 'MIN')
            counter_align = node.get('counterAxisAlignItems', 'MIN')
            if primary_align == 'SPACE_BETWEEN':
                layout_hints.append("Use Arrangement.SpaceBetween for distributed spacing")
            elif primary_align == 'CENTER':
                layout_hints.append("Center items along main axis with Arrangement.Center")
            if counter_align == 'CENTER':
                layout_hints.append("Center items along cross axis with Alignment.CenterHorizontally/CenterVertically")

        else:
            # Default CSS hints
            direction = 'row' if layout_mode == 'HORIZONTAL' else 'column'
            layout_hints.append(f"Use flexbox with flex-direction: {direction}")

            # Check for wrapping
            if node.get('layoutWrap') == 'WRAP':
                layout_hints.append("Enable flex-wrap for responsive wrapping")

            # Check for alignment
            primary_align = node.get('primaryAxisAlignItems', 'MIN')
            counter_align = node.get('counterAxisAlignItems', 'MIN')
            if primary_align == 'SPACE_BETWEEN':
                layout_hints.append("Use justify-content: space-between for distributed spacing")
            elif primary_align == 'CENTER':
                layout_hints.append("Center items along main axis")
            if counter_align == 'CENTER':
                layout_hints.append("Center items along cross axis")

    # Check for grid-like layouts (multiple children with same size)
    children = node.get('children', [])
    if len(children) >= 3:
        child_widths = [c.get('absoluteBoundingBox', {}).get('width', 0) for c in children if c.get('absoluteBoundingBox')]
        if child_widths and len(set(round(w) for w in child_widths)) == 1:
            if framework in ('swiftui',):
                layout_hints.append(f"Consider LazyVGrid with {len(children)}-column GridItem layout")
            elif framework in ('kotlin',):
                layout_hints.append(f"Consider LazyVerticalGrid with {len(children)} columns")
            else:
                layout_hints.append(f"Consider CSS Grid with {len(children)}-column layout")

    # Responsive hints based on size
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 0)
    if width > 1200:
        responsive_hints.append("Large container - consider max-width constraint for readability")
    if width > 768:
        responsive_hints.append("Below 768px: Consider stacking layout vertically")

    # Check for percentage-based constraints
    constraints = node.get('constraints', {})
    if constraints.get('horizontal') == 'SCALE':
        responsive_hints.append("Width scales with parent - use percentage or flex-grow")
    if constraints.get('vertical') == 'SCALE':
        responsive_hints.append("Height scales with parent - use percentage or flex-grow")

    # Interaction hints
    if interactions:
        for interaction in interactions:
            trigger = interaction.get('trigger', {}).get('type', '')
            action = interaction.get('action', {})
            action_type = action.get('type', '')
            transition = action.get('transition', {})

            if trigger == 'ON_HOVER':
                if action_type == 'NODE' and transition:
                    duration = transition.get('duration', 300)
                    easing = transition.get('easing', {}).get('type', 'ease-out').lower().replace('_', '-')
                    interaction_hints.append(f"Add hover transition: {duration}ms {easing}")
            elif trigger == 'ON_CLICK':
                if action_type == 'URL':
                    url = action.get('url', '')
                    interaction_hints.append(f"Click opens URL: {url}")
                elif action_type == 'NAVIGATE':
                    dest_id = action.get('destinationId', '')
                    interaction_hints.append(f"Click navigates to screen (node: {dest_id})")
            elif trigger == 'ON_PRESS':
                interaction_hints.append("Add active/pressed state styling")

    # Accessibility hints
    # Check for icon-only elements that need labels
    if 'icon' in node_name.lower() or 'btn' in node_name.lower():
        accessibility_hints.append("Add aria-label for screen readers")

    # Check text contrast
    fills = node.get('fills', [])
    for fill in fills:
        if fill.get('type') == 'SOLID' and fill.get('visible', True):
            color = fill.get('color', {})
            # Check if it's light text on light background
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if luminance > 0.7:
                accessibility_hints.append("Light color - ensure sufficient contrast with background (WCAG 4.5:1)")
            elif luminance < 0.3:
                accessibility_hints.append("Dark color - ensure sufficient contrast with background (WCAG 4.5:1)")

    # Check touch target size
    if bbox.get('width', 100) < 44 or bbox.get('height', 100) < 44:
        if any(keyword in node_name.lower() for keyword in ['button', 'btn', 'icon', 'link', 'tap']):
            accessibility_hints.append("Touch target may be too small - minimum 44x44px recommended")

    # Component hints
    if node_type == 'INSTANCE':
        component_props = node.get('componentProperties', {})
        variant_props = node.get('variantProperties', {})

        if variant_props:
            variants_str = ', '.join([f"{k}={v}" for k, v in variant_props.items()])
            component_hints.append(f"Component variant: {variants_str}")

        if component_props:
            props_str = ', '.join(component_props.keys())
            component_hints.append(f"Exposed props: {props_str}")

    elif node_type == 'COMPONENT':
        prop_defs = node.get('componentPropertyDefinitions', {})
        if prop_defs:
            component_hints.append(f"Component has {len(prop_defs)} customizable properties")

    elif node_type == 'COMPONENT_SET':
        component_hints.append("This is a component set with multiple variants")

    # Build result with non-empty sections
    if layout_hints:
        hints['layout'] = layout_hints
    if responsive_hints:
        hints['responsive'] = responsive_hints
    if interaction_hints:
        hints['interactions'] = interaction_hints
    if accessibility_hints:
        hints['accessibility'] = accessibility_hints
    if component_hints:
        hints['components'] = component_hints

    return hints if hints else None


def _check_accessibility(node: Dict[str, Any], parent_fills: Optional[List] = None) -> Dict[str, Any]:
    """Check accessibility issues for a node.

    Returns contrast issues, touch target warnings, and missing labels.
    """
    issues: Dict[str, Any] = {
        'contrast_issues': [],
        'touch_target_warnings': [],
        'label_warnings': []
    }

    node_name = node.get('name', '')
    node_type = node.get('type', '')
    bbox = node.get('absoluteBoundingBox', {})

    # Touch target size check for interactive elements
    interactive_keywords = ['button', 'btn', 'icon', 'link', 'tap', 'click', 'toggle', 'checkbox', 'radio', 'switch']
    is_interactive = any(keyword in node_name.lower() for keyword in interactive_keywords)

    if is_interactive and bbox:
        width = bbox.get('width', 100)
        height = bbox.get('height', 100)

        if width < 44 or height < 44:
            issues['touch_target_warnings'].append({
                'type': 'SMALL_TOUCH_TARGET',
                'message': f'Touch target too small ({width}x{height}px). Minimum recommended: 44x44px',
                'severity': 'warning',
                'wcag': 'WCAG 2.5.5 Target Size'
            })

        if width < 24 or height < 24:
            issues['touch_target_warnings'].append({
                'type': 'CRITICAL_TOUCH_TARGET',
                'message': f'Touch target critically small ({width}x{height}px). May be unusable.',
                'severity': 'error',
                'wcag': 'WCAG 2.5.5 Target Size'
            })

    # Label warnings for icon-only buttons
    if is_interactive and ('icon' in node_name.lower() or node_type == 'VECTOR'):
        # Check if there's no text child
        children = node.get('children', [])
        has_text = any(c.get('type') == 'TEXT' for c in children)
        if not has_text:
            issues['label_warnings'].append({
                'type': 'MISSING_LABEL',
                'message': 'Icon-only interactive element may need aria-label',
                'severity': 'warning',
                'wcag': 'WCAG 1.1.1 Non-text Content'
            })

    # Contrast ratio check for text nodes
    if node_type == 'TEXT':
        fills = node.get('fills', [])

        for fill in fills:
            if fill.get('type') == 'SOLID' and fill.get('visible', True):
                color = fill.get('color', {})
                r = int(color.get('r', 0) * 255)
                g = int(color.get('g', 0) * 255)
                b = int(color.get('b', 0) * 255)
                text_rgb = (r, g, b)

                # Calculate contrast against white and black backgrounds
                white_contrast = _contrast_ratio(text_rgb, (255, 255, 255))
                black_contrast = _contrast_ratio(text_rgb, (0, 0, 0))

                # Get font size for threshold determination
                style = node.get('style', {})
                font_size = style.get('fontSize', 16)
                font_weight = style.get('fontWeight', 400)

                # Large text threshold: 18pt (24px) or 14pt (18.66px) bold
                is_large_text = font_size >= 24 or (font_size >= 18.66 and font_weight >= 700)
                min_contrast = 3.0 if is_large_text else 4.5

                # Check if contrast might be insufficient
                hex_color = f"#{r:02x}{g:02x}{b:02x}"

                if white_contrast < min_contrast and black_contrast < min_contrast:
                    issues['contrast_issues'].append({
                        'type': 'LOW_CONTRAST',
                        'message': f'Text color {hex_color} may have insufficient contrast',
                        'severity': 'warning',
                        'wcag': 'WCAG 1.4.3 Contrast (Minimum)',
                        'details': {
                            'textColor': hex_color,
                            'contrastVsWhite': white_contrast,
                            'contrastVsBlack': black_contrast,
                            'required': min_contrast,
                            'isLargeText': is_large_text
                        }
                    })

                # Warn about very low contrast colors
                luminance = 0.2126 * (r/255) + 0.7152 * (g/255) + 0.0722 * (b/255)
                if 0.35 < luminance < 0.65:  # Mid-range colors are problematic
                    issues['contrast_issues'].append({
                        'type': 'MEDIUM_GRAY_TEXT',
                        'message': f'Mid-gray text ({hex_color}) often fails contrast requirements',
                        'severity': 'info',
                        'wcag': 'WCAG 1.4.3 Contrast (Minimum)'
                    })

    # Clean up empty arrays
    result = {k: v for k, v in issues.items() if v}
    return result if result else None


# ============================================================================
# CSS Code Generation Helpers
# ============================================================================

def _gradient_to_css(fill: Dict[str, Any]) -> Optional[str]:
    """Convert Figma gradient fill to CSS gradient string."""
    fill_type = fill.get('type', '')

    if 'GRADIENT' not in fill_type:
        return None

    gradient_stops = fill.get('gradientStops', [])
    if not gradient_stops:
        return None

    # Build color stops string
    stops_css = []
    for stop in gradient_stops:
        color = stop.get('color', {})
        position = stop.get('position', 0)
        hex_color = _rgba_to_hex(color)
        alpha = color.get('a', 1)
        if alpha < 1:
            # Use rgba for transparency
            r = int(color.get('r', 0) * 255)
            g = int(color.get('g', 0) * 255)
            b = int(color.get('b', 0) * 255)
            stops_css.append(f"rgba({r}, {g}, {b}, {alpha:.2f}) {int(position * 100)}%")
        else:
            stops_css.append(f"{hex_color} {int(position * 100)}%")

    stops_str = ', '.join(stops_css)

    if fill_type == 'GRADIENT_LINEAR':
        # Calculate angle from gradient handle positions
        handle_positions = fill.get('gradientHandlePositions', [])
        angle = _calculate_gradient_angle(handle_positions)
        return f"linear-gradient({int(angle)}deg, {stops_str})"

    elif fill_type == 'GRADIENT_RADIAL':
        return f"radial-gradient(circle, {stops_str})"

    elif fill_type == 'GRADIENT_ANGULAR':
        return f"conic-gradient({stops_str})"

    elif fill_type == 'GRADIENT_DIAMOND':
        # Diamond gradient approximated as radial
        return f"radial-gradient(ellipse, {stops_str})"

    return None


def _corner_radii_to_css(node: Dict[str, Any]) -> str:
    """Convert Figma corner radii to CSS border-radius."""
    # Check for individual corner radii
    if 'rectangleCornerRadii' in node:
        radii = node['rectangleCornerRadii']
        if len(radii) == 4:
            tl, tr, br, bl = radii
            if tl == tr == br == bl:
                return f"{int(tl)}px"
            return f"{int(tl)}px {int(tr)}px {int(br)}px {int(bl)}px"

    # Fallback to single cornerRadius
    corner_radius = node.get('cornerRadius', 0)
    if corner_radius:
        return f"{int(corner_radius)}px"

    return ""


def _transform_to_css(node: Dict[str, Any]) -> Optional[str]:
    """Convert Figma transform properties to CSS transform."""
    transforms = []

    # Rotation
    rotation = node.get('rotation', 0)
    if rotation:
        # Figma uses clockwise rotation in radians, CSS uses counter-clockwise degrees
        angle_deg = -rotation * (180 / 3.14159265359)
        if abs(angle_deg) > 0.1:  # Only add if significant
            transforms.append(f"rotate({angle_deg:.1f}deg)")

    # relativeTransform matrix (skew, scale, flip)
    relative_transform = node.get('relativeTransform')
    if relative_transform and len(relative_transform) >= 2:
        # relativeTransform is [[a, b, tx], [c, d, ty]]
        a = relative_transform[0][0] if len(relative_transform[0]) > 0 else 1
        b = relative_transform[0][1] if len(relative_transform[0]) > 1 else 0
        c = relative_transform[1][0] if len(relative_transform[1]) > 0 else 0
        d = relative_transform[1][1] if len(relative_transform[1]) > 1 else 1

        # Detect horizontal/vertical flip (negative scale values)
        if a < -0.01:
            transforms.append("scaleX(-1)")
        if d < -0.01:
            transforms.append("scaleY(-1)")

        # Check for non-unit scale (use absolute values since flip handled above)
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
        'PASS_THROUGH': None,  # Default, no CSS needed
        'NORMAL': None,
        'DARKEN': 'darken',
        'MULTIPLY': 'multiply',
        'LINEAR_BURN': 'color-burn',
        'COLOR_BURN': 'color-burn',
        'LIGHTEN': 'lighten',
        'SCREEN': 'screen',
        'LINEAR_DODGE': 'color-dodge',
        'COLOR_DODGE': 'color-dodge',
        'OVERLAY': 'overlay',
        'SOFT_LIGHT': 'soft-light',
        'HARD_LIGHT': 'hard-light',
        'DIFFERENCE': 'difference',
        'EXCLUSION': 'exclusion',
        'HUE': 'hue',
        'SATURATION': 'saturation',
        'COLOR': 'color',
        'LUMINOSITY': 'luminosity'
    }
    return blend_map.get(blend_mode)


def _text_case_to_css(text_case: str) -> Optional[str]:
    """Convert Figma textCase to CSS text-transform."""
    case_map = {
        'ORIGINAL': None,
        'UPPER': 'uppercase',
        'LOWER': 'lowercase',
        'TITLE': 'capitalize',
        'SMALL_CAPS': None,  # Requires font-variant: small-caps
        'SMALL_CAPS_FORCED': None
    }
    return case_map.get(text_case)


def _text_decoration_to_css(decoration: str) -> Optional[str]:
    """Convert Figma textDecoration to CSS text-decoration."""
    decoration_map = {
        'NONE': None,
        'UNDERLINE': 'underline',
        'STRIKETHROUGH': 'line-through'
    }
    return decoration_map.get(decoration)


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
            # Individual stroke weights
            ind_weights = strokes.get('individualWeights')
            if ind_weights:
                for side, w in ind_weights.items():
                    result[f'border-{side}'] = f"{w}px {style} {color_css}"
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


def _build_css_ready_shadow(effects: Optional[Dict[str, Any]], node_opacity: float = 1.0) -> Optional[Dict[str, str]]:
    """Build CSS-ready shadow and blur properties from effects."""
    if not effects:
        return None
    result = {}
    shadows = effects.get('shadows') or []
    blurs = effects.get('blurs') or []
    if shadows:
        box_shadows = []
        for shadow in shadows:
            shadow_type = shadow.get('type', 'DROP_SHADOW')
            offset = shadow.get('offset', {'x': 0, 'y': 0})
            radius = shadow.get('radius', 0)
            spread = shadow.get('spread', 0)
            hex_color = shadow.get('hex', shadow.get('color', '#000000'))
            rgb = _hex_to_rgb(hex_color)
            # Preserve shadow's own alpha channel (common in Figma: rgba(0,0,0,0.25))
            # hex_color may contain alpha info; check if original color had alpha
            shadow_opacity = shadow.get('opacity', 1)
            effective_shadow_opacity = shadow_opacity * node_opacity
            color_str = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {effective_shadow_opacity:.2f})"
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


def _build_css_ready_layout(auto_layout: Optional[Dict[str, Any]], bounds: Optional[Dict[str, Any]], size_constraints: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Build CSS-ready layout properties from auto-layout, bounds and constraints."""
    result = {}
    if auto_layout:
        mode = auto_layout.get('mode', 'HORIZONTAL')
        result['display'] = 'flex'
        result['flex-direction'] = 'row' if mode == 'HORIZONTAL' else 'column'
        gap = auto_layout.get('gap', 0)
        if gap:
            result['gap'] = f"{int(gap)}px"
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
        primary = auto_layout.get('primaryAxisAlign', 'MIN')
        counter = auto_layout.get('counterAxisAlign', 'MIN')
        align_map = {'MIN': 'flex-start', 'CENTER': 'center', 'MAX': 'flex-end', 'SPACE_BETWEEN': 'space-between'}
        result['justify-content'] = align_map.get(primary, 'flex-start')
        result['align-items'] = align_map.get(counter, 'flex-start')
        wrap = auto_layout.get('layoutWrap', 'NO_WRAP')
        if wrap == 'WRAP':
            result['flex-wrap'] = 'wrap'
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
        w = bounds.get('width', 0)
        h = bounds.get('height', 0)
        if w:
            result['width'] = f"{int(w)}px"
        if h:
            result['height'] = f"{int(h)}px"
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
    if family and size:
        lh_part = f"/{int(line_height)}px" if line_height else ''
        result['font'] = f"{int(weight)} {int(size)}px{lh_part} '{family}', sans-serif"
    if family:
        result['font-family'] = f"'{family}', sans-serif"
    if size:
        result['font-size'] = f"{int(size)}px"
    if weight:
        result['font-weight'] = str(int(weight))
    if line_height:
        result['line-height'] = f"{int(line_height)}px"
    if letter_spacing:
        result['letter-spacing'] = f"{letter_spacing:.2f}px"
    if text_align:
        align_map = {'LEFT': 'left', 'CENTER': 'center', 'RIGHT': 'right', 'JUSTIFIED': 'justify'}
        css_align = align_map.get(text_align)
        if css_align:
            result['text-align'] = css_align
    if text_case and text_case != 'ORIGINAL':
        css_case = _text_case_to_css(text_case)
        if css_case:
            result['text-transform'] = css_case
    if text_decoration and text_decoration != 'NONE':
        css_dec = _text_decoration_to_css(text_decoration)
        if css_dec:
            result['text-decoration'] = css_dec
    return result if result else None


def _transform_to_css_from_details(transform: Dict[str, Any]) -> Optional[str]:
    """Convert extracted transform details to CSS transform string."""
    parts = []
    if transform.get('flippedHorizontally'):
        parts.append("scaleX(-1)")
    if transform.get('flippedVertically'):
        parts.append("scaleY(-1)")
    rotation = transform.get('rotation', 0)
    if rotation:
        angle_deg = -rotation * (180 / 3.14159265359)
        if abs(angle_deg) > 0.1:
            parts.append(f"rotate({angle_deg:.1f}deg)")
    return ' '.join(parts) if parts else None


def _build_css_ready_section(node_details: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Build complete CSS-ready properties dict from node details.
    Combines all extracted design properties into CSS shorthand values
    that AI can directly use for code generation.
    """
    css = {}
    node_opacity = node_details.get('opacity', 1)
    # Note: CSS opacity applies to the entire element, so we don't fold
    # node_opacity into individual color values. Instead we set opacity
    # separately and use fill/stroke opacities only for colors.
    # Background/Color
    fills = node_details.get('fills', [])
    bg_css = _build_css_ready_background(fills, 1.0)
    if bg_css:
        if node_details.get('type') == 'TEXT':
            css['color'] = bg_css
        else:
            css['background'] = bg_css
    # Opacity (applied to entire element by browser)
    if node_opacity < 1:
        css['opacity'] = f"{node_opacity}"
    # Border (don't apply node_opacity to border colors; CSS opacity handles it)
    border_css = _build_css_ready_border(
        node_details.get('strokes'),
        node_details.get('cornerRadius'),
        1.0
    )
    if border_css:
        css.update(border_css)
    # Shadow & Blur (shadows are rendered outside opacity context, so apply node_opacity)
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
    # Overflow
    if node_details.get('clipsContent'):
        css['overflow'] = 'hidden'
    # Blend mode
    blend_mode = node_details.get('blendMode')
    if blend_mode:
        css_blend = _blend_mode_to_css(blend_mode)
        if css_blend:
            css['mix-blend-mode'] = css_blend
    return css if css else None


def _text_case_to_swiftui(text_case: str) -> Optional[str]:
    """Convert Figma textCase to SwiftUI modifier."""
    case_map = {
        'UPPER': '.textCase(.uppercase)',
        'LOWER': '.textCase(.lowercase)',
        'TITLE': '.textCase(.titleCase)'  # iOS 17+
    }
    return case_map.get(text_case)


def _text_case_to_kotlin(text_case: str) -> Optional[str]:
    """Convert Figma textCase to Kotlin/Compose text transformation."""
    case_map = {
        'UPPER': 'text.uppercase()',
        'LOWER': 'text.lowercase()',
        'TITLE': 'text.split(" ").joinToString(" ") { it.capitalize() }'
    }
    return case_map.get(text_case)


def _get_single_fill_css(fill: Dict[str, Any]) -> Optional[str]:
    """Convert a single fill to CSS value.

    Returns:
        CSS value string for the fill, or None if not visible
    """
    if not fill.get('visible', True):
        return None

    fill_type = fill.get('type', '')

    if fill_type == 'SOLID':
        color = fill.get('color', {})
        opacity = fill.get('opacity', 1)
        hex_color = _rgba_to_hex(color)

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
        # Return placeholder for image - will be resolved with actual URL later
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


def _get_background_css(node: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract background CSS (color or gradient) from node fills.

    For single fills, returns the simple value.
    For multiple fills, returns layered CSS background.

    Returns:
        tuple: (background_value, background_type) where type is 'color', 'gradient', 'image', or 'layered'
    """
    fills = node.get('fills', [])
    if not fills:
        return None, None

    # Collect all visible fills as CSS values
    # Figma fills are ordered bottom-to-top, CSS backgrounds are top-to-bottom
    # So we need to reverse the order
    css_values = []
    fill_types = []

    for fill in fills:
        css_value = _get_single_fill_css(fill)
        if css_value:
            css_values.append(css_value)
            fill_type = fill.get('type', 'SOLID')
            if 'GRADIENT' in fill_type:
                fill_types.append('gradient')
            elif fill_type == 'IMAGE':
                fill_types.append('image')
            else:
                fill_types.append('color')

    if not css_values:
        return None, None

    # Single fill - return simple value with type
    if len(css_values) == 1:
        return css_values[0], fill_types[0]

    # Multiple fills - reverse order (Figma bottom-to-top → CSS top-to-bottom)
    # and combine into layered background
    css_values.reverse()
    fill_types.reverse()

    # Join with comma for CSS layered background
    layered_css = ', '.join(css_values)

    return layered_css, 'layered'


# ============================================================================
# Design Token Code Generation Helpers
# ============================================================================

def _sanitize_token_name(name: str) -> str:
    """Sanitize token name for use in CSS/SCSS variables and Tailwind config."""
    # Convert to lowercase, replace spaces and special chars with hyphens
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    return sanitized or 'unnamed'


def _generate_style_variables(
    colors: List[Dict],
    typography: List[Dict],
    spacing: List[Dict],
    effects: List[Dict],
    format: Literal['css', 'scss'] = 'css'
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

    lines = []

    # Header
    if is_css:
        lines.append(":root {")
        lines.append(comment("Colors"))
    else:
        lines.extend(["// Design Tokens - Generated from Figma", "", "// Colors"])

    # Colors (deduplicated)
    seen_colors = set()
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
        seen_fonts = set()
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
        seen_spacing = set()
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
        seen_shadows = set()
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


def _generate_css_variables(colors: List[Dict], typography: List[Dict], spacing: List[Dict], effects: List[Dict]) -> str:
    """Generate CSS custom properties from design tokens."""
    return _generate_style_variables(colors, typography, spacing, effects, format='css')


def _generate_scss_variables(colors: List[Dict], typography: List[Dict], spacing: List[Dict], effects: List[Dict]) -> str:
    """Generate SCSS variables from design tokens."""
    return _generate_style_variables(colors, typography, spacing, effects, format='scss')


def _generate_tailwind_config(colors: List[Dict], typography: List[Dict], spacing: List[Dict]) -> str:
    """Generate Tailwind CSS theme extension from design tokens."""
    # Collect unique colors
    color_entries = {}
    for color in colors:
        hex_val = color.get('hex') or color.get('color', '')
        if hex_val and not hex_val.startswith('/*') and not hex_val.startswith('rgba'):
            name = _sanitize_token_name(color.get('name', 'color'))
            if name not in color_entries:
                color_entries[name] = hex_val

    # Collect font families
    font_entries = {}
    for typo in typography:
        font_family = typo.get('fontFamily', '')
        if font_family:
            name = _sanitize_token_name(font_family)
            if name not in font_entries:
                font_entries[name] = f"['{font_family}', 'sans-serif']"

    # Collect spacing values
    spacing_entries = {}
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


def _extract_colors_from_node(node: Dict[str, Any], colors: List[Dict[str, Any]]) -> None:
    """Recursively extract colors from node tree with full gradient and image support."""
    node_name = node.get('name', 'Unknown')

    # Fill colors (with gradient and image support)
    fills = node.get('fills', [])
    for fill in fills:
        fill_data = _extract_fill_data(fill, node_name)
        if fill_data:
            colors.append(fill_data)

    # Stroke colors (using comprehensive stroke extraction)
    stroke_data = _extract_stroke_data(node)
    if stroke_data and stroke_data['colors']:
        for stroke_color in stroke_data['colors']:
            colors.append({
                'name': node_name,
                'category': 'stroke',
                'fillType': stroke_color.get('type', 'SOLID'),
                'color': stroke_color.get('color'),
                'gradient': stroke_color.get('gradient'),
                'opacity': stroke_color.get('opacity', 1),
                'blendMode': stroke_color.get('blendMode', 'NORMAL'),
                'strokeWeight': stroke_data['weight'],
                'strokeAlign': stroke_data['align']
            })

    # Shadow colors
    effects_data = _extract_effects_data(node)
    if effects_data['shadows']:
        for shadow in effects_data['shadows']:
            colors.append({
                'name': node_name,
                'category': 'shadow',
                'fillType': 'SOLID',
                'color': shadow['color'],
                'shadowType': shadow['type'],
                'offset': shadow['offset'],
                'radius': shadow['radius'],
                'spread': shadow['spread']
            })

    # Recurse into children
    for child in node.get('children', []):
        _extract_colors_from_node(child, colors)


def _extract_typography_from_node(node: Dict[str, Any], typography: List[Dict[str, Any]]) -> None:
    """Recursively extract typography from node tree with advanced text properties."""
    if node.get('type') == 'TEXT':
        style = node.get('style', {})

        # Extract text fills for color
        fills = node.get('fills', [])
        text_color = None
        text_gradient = None
        for fill in fills:
            if fill.get('visible', True):
                if fill.get('type') == 'SOLID':
                    text_color = _rgba_to_hex(fill.get('color', {}))
                elif fill.get('type', '').startswith('GRADIENT_'):
                    text_gradient = {
                        'type': fill.get('type').replace('GRADIENT_', ''),
                        'stops': _extract_gradient_stops(fill.get('gradientStops', []))
                    }
                break

        typography.append({
            'name': node.get('name', 'Unknown'),
            'characters': node.get('characters', ''),

            # Font properties
            'fontFamily': style.get('fontFamily', 'Unknown'),
            'fontWeight': style.get('fontWeight', 400),
            'fontSize': style.get('fontSize', 16),
            'fontStyle': style.get('italic', False) and 'italic' or 'normal',

            # Spacing
            'lineHeight': style.get('lineHeightPx'),
            'lineHeightUnit': style.get('lineHeightUnit', 'PIXELS'),
            'lineHeightPercent': style.get('lineHeightPercent'),
            'letterSpacing': style.get('letterSpacing', 0),
            'paragraphSpacing': style.get('paragraphSpacing', 0),
            'paragraphIndent': style.get('paragraphIndent', 0),

            # Alignment
            'textAlign': style.get('textAlignHorizontal', 'LEFT'),
            'textAlignVertical': style.get('textAlignVertical', 'TOP'),

            # Decoration
            'textCase': style.get('textCase', 'ORIGINAL'),
            'textDecoration': style.get('textDecoration', 'NONE'),

            # Auto-resize
            'textAutoResize': node.get('textAutoResize', 'NONE'),

            # Truncation
            'textTruncation': node.get('textTruncation', 'DISABLED'),
            'maxLines': node.get('maxLines'),

            # Color
            'color': text_color,
            'gradient': text_gradient,

            # OpenType features
            'openTypeFeatures': style.get('openTypeFeatures', {}),

            # Hyperlink
            'hyperlink': node.get('hyperlink')
        })

    for child in node.get('children', []):
        _extract_typography_from_node(child, typography)


def _extract_spacing_from_node(node: Dict[str, Any], spacing: List[Dict[str, Any]]) -> None:
    """Recursively extract spacing/padding from node tree with advanced layout properties."""
    node_name = node.get('name', 'Unknown')

    # Auto-layout properties (comprehensive)
    auto_layout = _extract_auto_layout(node)
    if auto_layout:
        spacing.append({
            'name': node_name,
            'type': 'auto-layout',
            **auto_layout
        })

    # Absolute bounds
    bbox = node.get('absoluteBoundingBox', {})
    if bbox:
        bounds_data = {
            'name': node_name,
            'type': 'bounds',
            'width': bbox.get('width', 0),
            'height': bbox.get('height', 0),
            'x': bbox.get('x', 0),
            'y': bbox.get('y', 0)
        }

        # Add size constraints if present
        size_constraints = _extract_size_constraints(node)
        if size_constraints:
            bounds_data['sizeConstraints'] = size_constraints

        # Add layout positioning for children in auto-layout
        if 'layoutAlign' in node:
            bounds_data['layoutAlign'] = node['layoutAlign']
        if 'layoutGrow' in node:
            bounds_data['layoutGrow'] = node['layoutGrow']
        if 'layoutPositioning' in node:
            bounds_data['layoutPositioning'] = node['layoutPositioning']

        spacing.append(bounds_data)

    # Layout constraints for responsive behavior
    constraints = _extract_constraints(node)
    if constraints:
        spacing.append({
            'name': node_name,
            'type': 'constraints',
            **constraints
        })

    for child in node.get('children', []):
        _extract_spacing_from_node(child, spacing)


def _extract_shadows_from_node(node: Dict[str, Any], shadows: List[Dict[str, Any]]) -> None:
    """Recursively extract all effects (shadows and blurs) from node tree."""
    effects_data = _extract_effects_data(node)
    node_name = node.get('name', 'Unknown')

    # Add shadows
    if effects_data['shadows']:
        for shadow in effects_data['shadows']:
            shadows.append({
                'name': node_name,
                'type': shadow['type'],
                'color': shadow['color'],
                'offset': shadow['offset'],
                'radius': shadow['radius'],
                'spread': shadow['spread'],
                'blendMode': shadow['blendMode'],
                'showShadowBehindNode': shadow['showShadowBehindNode']
            })

    # Add blurs
    if effects_data['blurs']:
        for blur in effects_data['blurs']:
            shadows.append({
                'name': node_name,
                'type': blur['type'],
                'radius': blur['radius']
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


def _node_has_downloadable_assets(node: Dict[str, Any]) -> bool:
    """Check if a node contains downloadable assets (images, vectors, icons)."""
    # Check for image fills
    fills = node.get('fills', [])
    for fill in fills:
        if fill.get('type') == 'IMAGE':
            return True

    # Check for export settings
    if node.get('exportSettings'):
        return True

    # Check if it's a vector type that could be an icon
    node_type = node.get('type', '')
    if node_type in ['VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'POLYGON', 'LINE']:
        return True

    # Check for icon-like naming patterns
    name = node.get('name', '').lower()
    icon_patterns = ['icon', 'logo', 'svg', 'asset', 'image', 'img', 'pic']
    if any(pattern in name for pattern in icon_patterns):
        return True

    return False


def _node_to_simplified_tree(
    node: Dict[str, Any],
    depth: int,
    current_depth: int = 0,
    include_empty_frames: bool = False,
    min_children_count: int = 0,
    mark_downloadable_assets: bool = True
) -> Optional[Dict[str, Any]]:
    """Convert Figma node to simplified tree structure with smart filtering."""
    node_type = node.get('type', '')
    children = node.get('children', [])

    # Filter logic for frames/groups
    container_types = ['FRAME', 'GROUP', 'SECTION', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE']
    is_container = node_type in container_types

    if is_container:
        # Skip empty frames if include_empty_frames is False
        if not include_empty_frames and len(children) == 0:
            return None

        # Skip frames with fewer children than min_children_count
        if min_children_count > 0 and len(children) < min_children_count:
            return None

    simplified = {
        'id': node.get('id'),
        'name': node.get('name'),
        'type': node_type
    }

    # Add bounds if available
    bbox = node.get('absoluteBoundingBox')
    if bbox:
        simplified['bounds'] = {
            'width': round(bbox.get('width', 0)),
            'height': round(bbox.get('height', 0))
        }

    # Mark downloadable assets
    if mark_downloadable_assets and _node_has_downloadable_assets(node):
        simplified['hasAsset'] = True

    # Add children if within depth limit
    if current_depth < depth and children:
        filtered_children = []
        for child in children:
            child_tree = _node_to_simplified_tree(
                child,
                depth,
                current_depth + 1,
                include_empty_frames,
                min_children_count,
                mark_downloadable_assets
            )
            if child_tree is not None:
                filtered_children.append(child_tree)

        if filtered_children:
            simplified['children'] = filtered_children

    return simplified


# ============================================================================
# MCP Tools
# ============================================================================

@_versioned_tool(
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
            - include_empty_frames (bool): Include frames with no children (default: False)
            - min_children_count (int): Minimum children required (default: 0)
            - mark_downloadable_assets (bool): Mark nodes with downloadable assets (default: True)

    Returns:
        str: File structure in requested format. Nodes with 'hasAsset: true' contain
             downloadable images, vectors, or icons.

    Examples:
        - "Get structure of file XYZ123" -> file_key="XYZ123", depth=2
        - Full URL works too: file_key="https://figma.com/design/XYZ123/MyFile"
        - Skip noise: include_empty_frames=False, min_children_count=1
    """
    try:
        data = await _make_figma_request(f"files/{params.file_key}")

        document = data.get('document', {})
        name = data.get('name', 'Unknown')
        last_modified = data.get('lastModified', 'Unknown')

        # Build simplified tree with filtering options
        tree = _node_to_simplified_tree(
            document,
            params.depth,
            current_depth=0,
            include_empty_frames=params.include_empty_frames,
            min_children_count=params.min_children_count,
            mark_downloadable_assets=params.mark_downloadable_assets
        )

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
            if node is None:
                return
            prefix = "  " * indent
            icon = "📄" if node.get('type') == 'DOCUMENT' else \
                   "📑" if node.get('type') == 'CANVAS' else \
                   "🖼️" if node.get('type') == 'FRAME' else \
                   "📦" if node.get('type') == 'COMPONENT' else \
                   "🔗" if node.get('type') == 'INSTANCE' else \
                   "📝" if node.get('type') == 'TEXT' else "•"

            bounds = node.get('bounds', {})
            size_str = f" ({bounds.get('width')}×{bounds.get('height')})" if bounds else ""

            # Add asset marker if node has downloadable assets
            asset_marker = " 🎨" if node.get('hasAsset') else ""

            lines.append(f"{prefix}{icon} **{node.get('name')}** `{node.get('id')}`{size_str}{asset_marker}")

            for child in node.get('children', []):
                format_tree(child, indent + 1)

        format_tree(tree)

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
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
    Get comprehensive details about a specific node in a Figma file.

    Retrieves all design properties including:
    - Dimensions and position
    - Fills (solid, gradient, image)
    - Strokes (color, weight, align, cap, join, dashes)
    - Effects (shadows, blurs)
    - Auto-layout properties
    - Corner radii (individual corners)
    - Constraints (responsive behavior)
    - Transform (rotation, scale)
    - Component/Instance info
    - Bound variables
    - Blend mode

    Args:
        params: FigmaNodeInput containing:
            - file_key (str): Figma file key
            - node_id (str): Node ID (e.g., '1:2' or '1-2')
            - response_format: 'markdown' or 'json'

    Returns:
        str: Comprehensive node details in requested format
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

        # Build comprehensive node details
        node_details = {
            'id': params.node_id,
            'name': node.get('name', 'Unknown'),
            'type': node.get('type'),
            'visible': node.get('visible', True),
            'locked': node.get('locked', False)
        }

        # Bounds (comprehensive: bounding box, render bounds, transform, size)
        bbox = node.get('absoluteBoundingBox', {})
        render_bounds = node.get('absoluteRenderBounds')  # Actual visual bounds including effects
        relative_transform = node.get('relativeTransform')
        node_size = node.get('size')

        if bbox:
            node_details['bounds'] = {
                'width': round(bbox.get('width', 0), 2),
                'height': round(bbox.get('height', 0), 2),
                'x': round(bbox.get('x', 0), 2),
                'y': round(bbox.get('y', 0), 2)
            }

            # Render bounds (includes effects like shadows - actual visual footprint)
            if render_bounds:
                node_details['bounds']['renderBounds'] = {
                    'width': round(render_bounds.get('width', 0), 2),
                    'height': round(render_bounds.get('height', 0), 2),
                    'x': round(render_bounds.get('x', 0), 2),
                    'y': round(render_bounds.get('y', 0), 2)
                }

            # Relative transform (2x3 transformation matrix)
            if relative_transform:
                node_details['bounds']['relativeTransform'] = relative_transform

            # Node size (width, height before transforms)
            if node_size:
                node_details['bounds']['size'] = {
                    'width': round(node_size.get('x', 0), 2),
                    'height': round(node_size.get('y', 0), 2)
                }

        # Blend mode
        if 'blendMode' in node:
            node_details['blendMode'] = node['blendMode']

        # Opacity
        if 'opacity' in node:
            node_details['opacity'] = node['opacity']

        # Fills (with gradient and image support)
        fills = node.get('fills', [])
        if fills:
            node_details['fills'] = []
            for fill in fills:
                fill_data = _extract_fill_data(fill, node.get('name', ''))
                if fill_data:
                    # Remove 'name' and 'category' for cleaner output
                    fill_data.pop('name', None)
                    fill_data.pop('category', None)
                    node_details['fills'].append(fill_data)

        # Strokes (comprehensive)
        stroke_data = _extract_stroke_data(node)
        if stroke_data:
            node_details['strokes'] = stroke_data

        # Corner radii (individual corners)
        corner_radii = _extract_corner_radii(node)
        if corner_radii:
            node_details['cornerRadius'] = corner_radii

        # Effects (shadows and blurs)
        effects_data = _extract_effects_data(node)
        if effects_data['shadows'] or effects_data['blurs']:
            node_details['effects'] = {
                k: v for k, v in effects_data.items() if v
            }

        # Auto-layout (comprehensive)
        auto_layout = _extract_auto_layout(node)
        if auto_layout:
            node_details['autoLayout'] = auto_layout

        # Size constraints
        size_constraints = _extract_size_constraints(node)
        if size_constraints:
            node_details['sizeConstraints'] = size_constraints

        # Layout constraints (responsive)
        constraints = _extract_constraints(node)
        if constraints:
            node_details['constraints'] = constraints

        # Transform (includes rotation, scale, flip detection)
        transform = _extract_transform(node)
        if transform.get('rotation') or transform.get('preserveRatio') or transform.get('flippedHorizontally') or transform.get('flippedVertically'):
            node_details['transform'] = transform

        # Clip content
        if 'clipsContent' in node:
            node_details['clipsContent'] = node['clipsContent']

        # Mask info
        mask_data = _extract_mask_data(node)
        if mask_data:
            node_details['mask'] = mask_data

        # Component/Instance info
        component_info = _extract_component_info(node)
        if component_info:
            node_details['component'] = component_info

        # Bound variables
        bound_variables = _extract_bound_variables(node)
        if bound_variables:
            node_details['boundVariables'] = bound_variables

        # Export settings
        export_settings = _extract_export_settings(node)
        if export_settings:
            node_details['exportSettings'] = export_settings

        # Interactions (prototype triggers and actions)
        interactions = _extract_interactions(node)
        if interactions:
            node_details['interactions'] = interactions

        # Vector paths (for SVG export)
        vector_paths = _extract_vector_paths(node)
        if vector_paths:
            node_details['vectorPaths'] = vector_paths

        # Image references (for image fill resolution)
        image_refs = _extract_image_references(node, params.file_key)
        if image_refs:
            node_details['imageReferences'] = image_refs

        # Text-specific properties
        if node.get('type') == 'TEXT':
            style = node.get('style', {})
            node_details['text'] = {
                'characters': node.get('characters', ''),
                'fontFamily': style.get('fontFamily'),
                'fontSize': style.get('fontSize'),
                'fontWeight': style.get('fontWeight'),
                'fontStyle': 'italic' if style.get('italic') else 'normal',
                'lineHeight': style.get('lineHeightPx'),
                'lineHeightUnit': style.get('lineHeightUnit'),
                'letterSpacing': style.get('letterSpacing'),
                'textAlign': style.get('textAlignHorizontal'),
                'textAlignVertical': style.get('textAlignVertical'),
                'textCase': style.get('textCase'),
                'textDecoration': style.get('textDecoration'),
                'paragraphSpacing': style.get('paragraphSpacing'),
                'paragraphIndent': style.get('paragraphIndent'),
                'textAutoResize': node.get('textAutoResize'),
                'textTruncation': node.get('textTruncation'),
                'maxLines': node.get('maxLines'),
                'hyperlink': node.get('hyperlink')
            }
            # Clean up None values
            node_details['text'] = {k: v for k, v in node_details['text'].items() if v is not None}

        # Implementation hints (AI-friendly guidance)
        hint_framework = params.framework or 'css'
        impl_hints = _generate_implementation_hints(node, interactions, framework=hint_framework)
        if impl_hints:
            node_details['implementationHints'] = impl_hints

        # Accessibility checks
        a11y_issues = _check_accessibility(node)
        if a11y_issues:
            node_details['accessibility'] = a11y_issues

        # Children with depth-2 traversal
        children = node.get('children', [])
        if children:
            node_details['childrenCount'] = len(children)
            node_details['children'] = _extract_children_summary(children, depth=0, max_depth=2)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(node_details, indent=2)

        # Markdown format
        lines = [
            f"# Node: {node_details['name']}",
            f"**ID:** `{node_details['id']}`",
            f"**Type:** {node_details['type']}",
            ""
        ]

        # Visibility/Lock status
        if not node_details.get('visible', True):
            lines.append("⚠️ **This node is hidden**\n")
        if node_details.get('locked', False):
            lines.append("🔒 **This node is locked**\n")

        # Bounds
        if 'bounds' in node_details:
            b = node_details['bounds']
            lines.extend([
                "## Dimensions",
                f"- **Width:** {b['width']}px",
                f"- **Height:** {b['height']}px",
                f"- **Position:** ({b['x']}, {b['y']})",
                ""
            ])

        # Blend mode & Opacity
        if 'blendMode' in node_details or 'opacity' in node_details:
            lines.append("## Appearance")
            if 'blendMode' in node_details:
                lines.append(f"- **Blend Mode:** {node_details['blendMode']}")
            if 'opacity' in node_details:
                lines.append(f"- **Opacity:** {node_details['opacity']}")
            lines.append("")

        # Fills
        if 'fills' in node_details:
            lines.append("## Fills")
            for fill in node_details['fills']:
                fill_type = fill.get('fillType', 'SOLID')
                if fill_type == 'SOLID':
                    fill_op = fill.get('opacity', 1)
                    node_op = node_details.get('opacity', 1)
                    effective_op = fill_op * node_op
                    opacity_info = f"opacity: {fill_op:.2f}"
                    if node_op < 1:
                        opacity_info += f" × node:{node_op:.2f} = effective:{effective_op:.2f}"
                    lines.append(f"- **Solid:** {fill.get('color')} ({opacity_info})")
                elif fill_type.startswith('GRADIENT_'):
                    gradient = fill.get('gradient', {})
                    stops = gradient.get('stops', [])
                    gradient_type = gradient.get('type', 'LINEAR')
                    angle = gradient.get('angle', 0)
                    colors = ' → '.join([s['color'] for s in stops[:3]])
                    if len(stops) > 3:
                        colors += f" (+{len(stops)-3} more)"
                    lines.append(f"- **{gradient_type} Gradient:** {colors}")
                    if gradient_type == 'LINEAR':
                        lines.append(f"  - Angle: {angle}°")
                elif fill_type == 'IMAGE':
                    image = fill.get('image', {})
                    lines.append(f"- **Image:** ref={image.get('imageRef')}, scale={image.get('scaleMode')}")
            bg_css = _build_css_ready_background(node_details['fills'], 1.0)
            if bg_css:
                prop_name = 'color' if node_details.get('type') == 'TEXT' else 'background'
                lines.append(f"- **CSS:** `{prop_name}: {bg_css};`")
            lines.append("")

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

        # Effects
        if 'effects' in node_details:
            lines.append("## Effects")
            if node_details['effects'].get('shadows'):
                for shadow in node_details['effects']['shadows']:
                    offset = shadow['offset']
                    lines.append(
                        f"- **{shadow['type']}:** {shadow['color']}, "
                        f"offset ({offset['x']}, {offset['y']}), "
                        f"blur {shadow['radius']}px, spread {shadow['spread']}px"
                    )
                    inset = 'inset ' if shadow['type'] == 'INNER_SHADOW' else ''
                    ox = int(offset.get('x', 0))
                    oy = int(offset.get('y', 0))
                    r = int(shadow['radius'])
                    sp = int(shadow['spread'])
                    lines.append(
                        f"  - `box-shadow: {inset}{ox}px {oy}px {r}px {sp}px {shadow.get('hex', shadow['color'])};`"
                    )
            if node_details['effects'].get('blurs'):
                for blur in node_details['effects']['blurs']:
                    lines.append(f"- **{blur['type']}:** {blur['radius']}px")
                    if blur['type'] == 'LAYER_BLUR':
                        lines.append(f"  - `filter: blur({int(blur['radius'])}px);`")
                    elif blur['type'] == 'BACKGROUND_BLUR':
                        lines.append(f"  - `backdrop-filter: blur({int(blur['radius'])}px);`")
            lines.append("")

        # Auto-layout
        if 'autoLayout' in node_details:
            al = node_details['autoLayout']
            mode = al['mode']
            direction = 'row' if mode == 'HORIZONTAL' else 'column'
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

        # Constraints
        if 'constraints' in node_details:
            c = node_details['constraints']
            lines.extend([
                "## Constraints (Responsive)",
                f"- **Horizontal:** {c['horizontal']}",
                f"- **Vertical:** {c['vertical']}",
                ""
            ])

        # Size constraints
        if 'sizeConstraints' in node_details:
            sc = node_details['sizeConstraints']
            lines.append("## Size Constraints")
            if 'minWidth' in sc:
                lines.append(f"- **Min Width:** {sc['minWidth']}px")
            if 'maxWidth' in sc:
                lines.append(f"- **Max Width:** {sc['maxWidth']}px")
            if 'minHeight' in sc:
                lines.append(f"- **Min Height:** {sc['minHeight']}px")
            if 'maxHeight' in sc:
                lines.append(f"- **Max Height:** {sc['maxHeight']}px")
            lines.append("")

        # Transform
        if 'transform' in node_details:
            t = node_details['transform']
            lines.append("## Transform")
            if t.get('rotation'):
                lines.append(f"- **Rotation:** {t['rotation']}°")
            if t.get('preserveRatio'):
                lines.append(f"- **Preserve Ratio:** Yes")
            if t.get('flippedHorizontally'):
                lines.append(f"- **Flipped Horizontally:** Yes (scaleX: -1)")
            if t.get('flippedVertically'):
                lines.append(f"- **Flipped Vertically:** Yes (scaleY: -1)")
            lines.append("")

        # Clip content
        if 'clipsContent' in node_details:
            lines.append(f"## Clip Content: {'Yes' if node_details['clipsContent'] else 'No'}\n")

        # Component info
        if 'component' in node_details:
            comp = node_details['component']
            lines.append("## Component Info")
            if comp.get('isInstance'):
                lines.append(f"- **Type:** Instance")
                lines.append(f"- **Component ID:** {comp.get('componentId')}")
                if comp.get('componentProperties'):
                    lines.append(f"- **Properties:** {json.dumps(comp['componentProperties'], indent=2)}")
            elif comp.get('isComponent'):
                lines.append(f"- **Type:** Component")
                if comp.get('componentSetId'):
                    lines.append(f"- **Component Set ID:** {comp['componentSetId']}")
            elif comp.get('isComponentSet'):
                lines.append(f"- **Type:** Component Set")
            lines.append("")

        # Bound variables
        if 'boundVariables' in node_details:
            lines.append("## Bound Variables")
            for prop, var in node_details['boundVariables'].items():
                if isinstance(var, list):
                    lines.append(f"- **{prop}:** {len(var)} variable(s) bound")
                else:
                    lines.append(f"- **{prop}:** {var.get('variableId')}")
            lines.append("")

        # Text properties
        if 'text' in node_details:
            txt = node_details['text']
            lines.append("## Text Properties")
            if txt.get('characters'):
                preview = txt['characters'][:50] + '...' if len(txt.get('characters', '')) > 50 else txt['characters']
                lines.append(f"- **Content:** \"{preview}\"")
            if txt.get('fontFamily'):
                lines.append(f"- **Font:** {txt['fontFamily']} {txt.get('fontWeight', 400)}")
            if txt.get('fontSize'):
                lines.append(f"- **Size:** {txt['fontSize']}px")
            if txt.get('lineHeight'):
                lines.append(f"- **Line Height:** {txt['lineHeight']}px")
            if txt.get('letterSpacing'):
                lines.append(f"- **Letter Spacing:** {txt['letterSpacing']}px")
            if txt.get('textAlign'):
                lines.append(f"- **Alignment:** {txt['textAlign']} / {txt.get('textAlignVertical', 'TOP')}")
            if txt.get('textCase') and txt['textCase'] != 'ORIGINAL':
                lines.append(f"- **Text Case:** {txt['textCase']}")
            if txt.get('textDecoration') and txt['textDecoration'] != 'NONE':
                lines.append(f"- **Decoration:** {txt['textDecoration']}")
            if txt.get('textAutoResize'):
                lines.append(f"- **Auto Resize:** {txt['textAutoResize']}")
            if txt.get('fontFamily') and txt.get('fontSize'):
                w = int(txt.get('fontWeight', 400))
                sz = int(txt['fontSize'])
                lh = f"/{int(txt['lineHeight'])}px" if txt.get('lineHeight') else ''
                fam = txt['fontFamily']
                lines.append(f"- **CSS:** `font: {w} {sz}px{lh} '{fam}', sans-serif;`")
            lines.append("")

        # CSS Ready Section (only for CSS-based frameworks)
        hint_framework = params.framework or 'css'
        if hint_framework not in ('swiftui', 'kotlin'):
            css_ready = _build_css_ready_section(node_details)
            if css_ready:
                lines.append("## CSS Ready")
                lines.append("```css")
                css_props = {k: v for k, v in css_ready.items() if not k.endswith('-note')}
                for prop, value in css_props.items():
                    lines.append(f"  {prop}: {value};")
                lines.append("```")
                notes = {k: v for k, v in css_ready.items() if k.endswith('-note')}
                for note_key, note_value in notes.items():
                    lines.append(f"> Note: {note_value}")
                lines.append("")

        # Implementation Hints
        if 'implementationHints' in node_details:
            hints = node_details['implementationHints']
            lines.append("## 🚀 Implementation Hints")
            if hints.get('layout'):
                lines.append("### Layout")
                for hint in hints['layout']:
                    lines.append(f"- {hint}")
            if hints.get('responsive'):
                lines.append("### Responsive")
                for hint in hints['responsive']:
                    lines.append(f"- {hint}")
            if hints.get('interactions'):
                lines.append("### Interactions")
                for hint in hints['interactions']:
                    lines.append(f"- {hint}")
            if hints.get('accessibility'):
                lines.append("### Accessibility")
                for hint in hints['accessibility']:
                    lines.append(f"- {hint}")
            if hints.get('components'):
                lines.append("### Components")
                for hint in hints['components']:
                    lines.append(f"- {hint}")
            lines.append("")

        # Accessibility Warnings
        if 'accessibility' in node_details:
            a11y = node_details['accessibility']
            lines.append("## ♿ Accessibility")
            if a11y.get('contrast_issues'):
                lines.append("### Contrast Issues")
                for issue in a11y['contrast_issues']:
                    severity_icon = "❌" if issue.get('severity') == 'error' else "⚠️" if issue.get('severity') == 'warning' else "ℹ️"
                    lines.append(f"- {severity_icon} {issue.get('message')}")
                    if issue.get('wcag'):
                        lines.append(f"  - WCAG: {issue['wcag']}")
            if a11y.get('touch_target_warnings'):
                lines.append("### Touch Target Issues")
                for issue in a11y['touch_target_warnings']:
                    severity_icon = "❌" if issue.get('severity') == 'error' else "⚠️"
                    lines.append(f"- {severity_icon} {issue.get('message')}")
                    if issue.get('wcag'):
                        lines.append(f"  - WCAG: {issue['wcag']}")
            if a11y.get('label_warnings'):
                lines.append("### Label Warnings")
                for issue in a11y['label_warnings']:
                    lines.append(f"- ⚠️ {issue.get('message')}")
                    if issue.get('wcag'):
                        lines.append(f"  - WCAG: {issue['wcag']}")
            lines.append("")

        # Children
        if 'children' in node_details:
            lines.append(f"## Children ({node_details.get('childrenCount', 0)} nodes)")
            lines.append("")
            _render_children_markdown(lines, node_details['children'], indent=0)
        elif 'childrenCount' in node_details:
            lines.append(f"**Children:** {node_details['childrenCount']} child node(s)")

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
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
        str: Local file paths for each screenshot
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

        # Create screenshots directory in temp folder
        screenshots_dir = Path(tempfile.gettempdir()) / "figma_screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        lines = [
            "# Generated Screenshots",
            f"**Format:** {params.format.value.upper()}",
            f"**Scale:** {params.scale}x",
            "",
            "## Local Files",
            ""
        ]

        # Download each image and save locally
        async with httpx.AsyncClient(timeout=60.0) as client:
            for node_id, url in images.items():
                if url:
                    try:
                        response = await client.get(url)
                        response.raise_for_status()

                        # Create filename from node_id and file_key
                        safe_node_id = node_id.replace(":", "-")
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"{params.file_key}_{safe_node_id}_{timestamp}.{params.format.value}"
                        filepath = screenshots_dir / filename

                        # Save the image
                        filepath.write_bytes(response.content)

                        lines.append(f"- **{node_id}**: `{filepath}`")
                    except httpx.HTTPStatusError as e:
                        lines.append(f"- **{node_id}**: HTTP error {e.response.status_code}")
                    except httpx.TimeoutException:
                        lines.append(f"- **{node_id}**: Download timed out")
                    except OSError as e:
                        lines.append(f"- **{node_id}**: File system error - {e.strerror}")
                    except Exception as e:
                        lines.append(f"- **{node_id}**: Unexpected error - {type(e).__name__}: {e}")
                else:
                    lines.append(f"- **{node_id}**: Failed to render")

        lines.extend([
            "",
            f"> Screenshots saved to: `{screenshots_dir}`"
        ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
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
            # Deduplicate by color value
            unique_colors = {}
            for c in colors:
                # Generate dedup key based on color type
                if c.get('hex'):
                    key = c['hex']
                elif c.get('color'):
                    key = c['color']
                elif c.get('gradient'):
                    key = str(c['gradient'])
                elif c.get('image'):
                    key = c['image'].get('imageRef', str(c['image']))
                else:
                    key = str(c)
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

        # Extract effects (shadows, blurs)
        if params.include_effects:
            shadows: List[Dict[str, Any]] = []
            _extract_shadows_from_node(node, shadows)
            # Separate shadows and blurs
            shadow_tokens = [s for s in shadows if 'SHADOW' in s.get('type', '')]
            blur_tokens = [s for s in shadows if 'BLUR' in s.get('type', '')]

            # Deduplicate shadows by value
            unique_shadows = {}
            for s in shadow_tokens:
                key = f"{s.get('color', '')}-{s.get('offsetX', 0)}-{s.get('offsetY', 0)}-{s.get('blur', 0)}"
                if key not in unique_shadows:
                    unique_shadows[key] = s
            tokens['shadows'] = list(unique_shadows.values())

            # Deduplicate blurs by value
            unique_blurs = {}
            for b in blur_tokens:
                key = f"{b.get('type', '')}-{b.get('radius', 0)}"
                if key not in unique_blurs:
                    unique_blurs[key] = b
            tokens['blurs'] = list(unique_blurs.values())

        # Format as design token standard
        formatted_tokens = {
            '$schema': 'https://design-tokens.github.io/community-group/format/',
            'figmaFile': params.file_key,
            'tokens': tokens
        }

        # Generate ready-to-use code if requested
        if params.include_generated_code:
            colors_list = tokens.get('colors', [])
            typography_list = tokens.get('typography', [])
            spacing_list = tokens.get('spacing', [])
            shadows_list = tokens.get('shadows', [])

            formatted_tokens['generated'] = {
                'css_variables': _generate_css_variables(colors_list, typography_list, spacing_list, shadows_list),
                'scss_variables': _generate_scss_variables(colors_list, typography_list, spacing_list, shadows_list),
                'tailwind_config': _generate_tailwind_config(colors_list, typography_list, shadows_list)
            }

        result = json.dumps(formatted_tokens, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            # Step 1: Remove generated code (CSS/SCSS/Tailwind) - usually the biggest chunk
            if 'generated' in formatted_tokens:
                del formatted_tokens['generated']
                result = json.dumps(formatted_tokens, indent=2)

            # Step 2: If still too large, limit each token category
            if len(result) > CHARACTER_LIMIT:
                max_per_category = 100
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

        return result

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
    name="figma_get_styles",
    annotations={
        "title": "Get Published Styles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_styles(params: FigmaStylesInput) -> str:
    """
    Retrieve all published styles from a Figma file.

    Fetches published color styles, text styles, effect styles, and grid styles
    from the file. These are reusable design tokens defined in Figma.

    Args:
        params: FigmaStylesInput containing:
            - file_key (str): Figma file key
            - include_fill_styles (bool): Include fill/color styles
            - include_text_styles (bool): Include text/typography styles
            - include_effect_styles (bool): Include effect styles
            - include_grid_styles (bool): Include grid/layout styles
            - response_format: 'markdown' or 'json'

    Returns:
        str: Published styles in requested format
    """
    try:
        # Fetch styles from the file styles endpoint
        data = await _make_figma_request(f"files/{params.file_key}/styles")

        styles = data.get('meta', {}).get('styles', [])

        if not styles:
            return "No published styles found in this file."

        # Categorize styles and collect node IDs
        fill_styles = []
        text_styles = []
        effect_styles = []
        grid_styles = []
        style_node_ids = []

        for style in styles:
            style_type = style.get('style_type', '')
            node_id = style.get('node_id', '')
            style_data = {
                'key': style.get('key', ''),
                'name': style.get('name', ''),
                'description': style.get('description', ''),
                'node_id': node_id,
                'created_at': style.get('created_at', ''),
                'updated_at': style.get('updated_at', ''),
                'sort_position': style.get('sort_position', '')
            }

            if style_type == 'FILL' and params.include_fill_styles:
                fill_styles.append(style_data)
                if node_id:
                    style_node_ids.append(node_id)
            elif style_type == 'TEXT' and params.include_text_styles:
                text_styles.append(style_data)
                if node_id:
                    style_node_ids.append(node_id)
            elif style_type == 'EFFECT' and params.include_effect_styles:
                effect_styles.append(style_data)
                if node_id:
                    style_node_ids.append(node_id)
            elif style_type == 'GRID' and params.include_grid_styles:
                grid_styles.append(style_data)
                if node_id:
                    style_node_ids.append(node_id)

        # Optimized: Fetch only the style nodes instead of entire file
        # This is much faster for large files with few styles
        nodes_data = {}
        doc_styles = {}
        if style_node_ids:
            nodes_response = await _make_figma_request(
                f"files/{params.file_key}/nodes",
                params={"ids": ",".join(style_node_ids)}
            )
            nodes_data = nodes_response.get('nodes', {})
            doc_styles = nodes_response.get('styles', {})

        # Enrich styles with actual values
        def enrich_style(style_data: Dict, doc_styles: Dict, nodes_data: Dict) -> Dict:
            node_id = style_data.get('node_id', '')
            if node_id and node_id in doc_styles:
                style_info = doc_styles[node_id]
                style_data['styleType'] = style_info.get('styleType', '')

            # Get node directly from nodes_data (optimized - no tree search)
            node = nodes_data.get(node_id, {}).get('document', {})
            if node:
                # Extract fill details
                if node.get('fills'):
                    fills_data = []
                    for fill in node.get('fills', []):
                        fill_info = _extract_fill_data(fill, style_data.get('name', ''))
                        if fill_info:
                            fills_data.append(fill_info)
                    if fills_data:
                        style_data['fills'] = fills_data

                # Extract text style details
                if node.get('style'):
                    style_data['textStyle'] = {
                        'fontFamily': node['style'].get('fontFamily'),
                        'fontWeight': node['style'].get('fontWeight'),
                        'fontSize': node['style'].get('fontSize'),
                        'lineHeightPx': node['style'].get('lineHeightPx'),
                        'letterSpacing': node['style'].get('letterSpacing'),
                        'textCase': node['style'].get('textCase'),
                        'textDecoration': node['style'].get('textDecoration')
                    }

                # Extract effect details
                if node.get('effects'):
                    effects_data = _extract_effects_data(node)
                    style_data['effects'] = effects_data

            return style_data

        # Enrich all styles
        fill_styles = [enrich_style(s, doc_styles, nodes_data) for s in fill_styles]
        text_styles = [enrich_style(s, doc_styles, nodes_data) for s in text_styles]
        effect_styles = [enrich_style(s, doc_styles, nodes_data) for s in effect_styles]
        grid_styles = [enrich_style(s, doc_styles, nodes_data) for s in grid_styles]

        # Format output
        if params.response_format == ResponseFormat.JSON:
            result = {
                'file_key': params.file_key,
                'total_styles': len(styles),
                'fill_styles': fill_styles if params.include_fill_styles else [],
                'text_styles': text_styles if params.include_text_styles else [],
                'effect_styles': effect_styles if params.include_effect_styles else [],
                'grid_styles': grid_styles if params.include_grid_styles else []
            }
            return json.dumps(result, indent=2)

        # Markdown format
        lines = [
            "# Published Styles",
            f"**File:** `{params.file_key}`",
            f"**Total Styles:** {len(styles)}",
            ""
        ]

        if fill_styles:
            lines.append("## 🎨 Fill/Color Styles")
            lines.append("")
            for style in fill_styles:
                lines.append(f"### {style['name']}")
                if style.get('description'):
                    lines.append(f"*{style['description']}*")
                if style.get('fills'):
                    for fill in style['fills']:
                        if fill.get('fillType') == 'SOLID':
                            lines.append(f"- **Color:** `{fill.get('color', 'N/A')}`")
                            if fill.get('opacity') is not None and fill['opacity'] < 1:
                                lines.append(f"- **Opacity:** {fill['opacity']}")
                        elif 'GRADIENT' in fill.get('fillType', ''):
                            lines.append(f"- **Type:** {fill['fillType']}")
                            if fill.get('gradient'):
                                grad = fill['gradient']
                                lines.append(f"- **Angle:** {grad.get('angle', 0)}°")
                                stops = grad.get('stops', [])
                                if stops:
                                    stop_str = ', '.join([f"{s['color']} at {int(s['position']*100)}%" for s in stops])
                                    lines.append(f"- **Stops:** {stop_str}")
                lines.append(f"- **Key:** `{style['key']}`")
                lines.append("")

        if text_styles:
            lines.append("## 📝 Text Styles")
            lines.append("")
            for style in text_styles:
                lines.append(f"### {style['name']}")
                if style.get('description'):
                    lines.append(f"*{style['description']}*")
                if style.get('textStyle'):
                    ts = style['textStyle']
                    if ts.get('fontFamily'):
                        lines.append(f"- **Font:** {ts['fontFamily']}")
                    if ts.get('fontWeight'):
                        lines.append(f"- **Weight:** {ts['fontWeight']}")
                    if ts.get('fontSize'):
                        lines.append(f"- **Size:** {ts['fontSize']}px")
                    if ts.get('lineHeightPx'):
                        lines.append(f"- **Line Height:** {ts['lineHeightPx']}px")
                    if ts.get('letterSpacing'):
                        lines.append(f"- **Letter Spacing:** {ts['letterSpacing']}")
                    if ts.get('textCase') and ts['textCase'] != 'ORIGINAL':
                        lines.append(f"- **Case:** {ts['textCase']}")
                    if ts.get('textDecoration') and ts['textDecoration'] != 'NONE':
                        lines.append(f"- **Decoration:** {ts['textDecoration']}")
                lines.append(f"- **Key:** `{style['key']}`")
                lines.append("")

        if effect_styles:
            lines.append("## ✨ Effect Styles")
            lines.append("")
            for style in effect_styles:
                lines.append(f"### {style['name']}")
                if style.get('description'):
                    lines.append(f"*{style['description']}*")
                if style.get('effects'):
                    effects = style['effects']
                    if effects.get('shadows'):
                        for shadow in effects['shadows']:
                            shadow_type = shadow.get('type', 'DROP_SHADOW')
                            lines.append(f"- **{shadow_type}:** {shadow.get('color', 'N/A')} offset({shadow.get('offsetX', 0)}, {shadow.get('offsetY', 0)}) blur({shadow.get('blur', 0)})")
                    if effects.get('blurs'):
                        for blur in effects['blurs']:
                            lines.append(f"- **{blur.get('type', 'BLUR')}:** radius {blur.get('radius', 0)}px")
                lines.append(f"- **Key:** `{style['key']}`")
                lines.append("")

        if grid_styles:
            lines.append("## 📐 Grid Styles")
            lines.append("")
            for style in grid_styles:
                lines.append(f"### {style['name']}")
                if style.get('description'):
                    lines.append(f"*{style['description']}*")
                lines.append(f"- **Key:** `{style['key']}`")
                lines.append("")

        result = "\n".join(lines)

        if len(result) > CHARACTER_LIMIT:
            return result[:CHARACTER_LIMIT] + "\n\n... (truncated)"

        return result

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
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
        # Use nodes endpoint to get full node tree with all properties
        # (files endpoint may omit relativeTransform needed for flip detection)
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

        if not node:
            return f"Error: Node '{params.node_id}' not found."

        # Generate component name
        component_name = params.component_name or _sanitize_component_name(node.get('name', 'Component'))

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
            from generators.swiftui_generator import generate_swiftui_code
            code = generate_swiftui_code(node, component_name)
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
            "```" + {"react": "tsx", "react_tailwind": "tsx", "vue": "vue", "vue_tailwind": "vue", "swiftui": "swift", "kotlin": "kotlin", "css": "css", "scss": "scss"}.get(params.framework.value, "html"),
            code,
            "```"
        ]

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


# ============================================================================
# Code Connect Tools
# ============================================================================

@_versioned_tool(
    name="figma_get_code_connect_map",
    annotations={
        "title": "Get Code Connect Mappings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def figma_get_code_connect_map(params: FigmaCodeConnectGetInput) -> str:
    """
    Get Code Connect mappings for a Figma file.

    Retrieves stored mappings between Figma components and code implementations.
    These mappings help generate accurate code by linking design components
    to their actual code counterparts.

    Args:
        params: FigmaCodeConnectGetInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node ID to get mapping for

    Returns:
        str: JSON formatted Code Connect mappings

    Examples:
        - Get all mappings for a file: file_key="ABC123"
        - Get specific mapping: file_key="ABC123", node_id="1:2"
    """
    try:
        data = _load_code_connect_data()
        mappings = data.get("mappings", {})
        file_mappings = mappings.get(params.file_key, {})

        if not file_mappings:
            return json.dumps({
                "status": "success",
                "file_key": params.file_key,
                "mappings": {},
                "message": f"No Code Connect mappings found for file '{params.file_key}'."
            }, indent=2)

        # If specific node_id requested
        if params.node_id:
            node_mapping = file_mappings.get(params.node_id)
            if node_mapping:
                return json.dumps({
                    "status": "success",
                    "file_key": params.file_key,
                    "node_id": params.node_id,
                    "mapping": node_mapping
                }, indent=2)
            else:
                return json.dumps({
                    "status": "not_found",
                    "file_key": params.file_key,
                    "node_id": params.node_id,
                    "message": f"No mapping found for node '{params.node_id}' in file '{params.file_key}'."
                }, indent=2)

        # Return all mappings for the file
        return json.dumps({
            "status": "success",
            "file_key": params.file_key,
            "mappings": file_mappings,
            "count": len(file_mappings)
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


@_versioned_tool(
    name="figma_add_code_connect_map",
    annotations={
        "title": "Add Code Connect Mapping",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def figma_add_code_connect_map(params: FigmaCodeConnectAddInput) -> str:
    """
    Add or update a Code Connect mapping for a Figma component.

    Creates a mapping between a Figma component (identified by file_key and node_id)
    and its code implementation. This mapping helps generate accurate code by
    providing context about component paths, prop mappings, and variants.

    Args:
        params: FigmaCodeConnectAddInput containing:
            - file_key (str): Figma file key
            - node_id (str): Figma node ID to map
            - component_path (str): Path to code component (e.g., 'src/components/Button.tsx')
            - component_name (str): Name of the component (e.g., 'Button')
            - props_mapping (Dict[str, str]): Mapping of Figma props to code props
            - variants (Dict[str, Dict]): Variant mappings
            - example (Optional[str]): Example usage code

    Returns:
        str: JSON formatted result with status

    Examples:
        - Add Button mapping:
          file_key="ABC123", node_id="1:2",
          component_path="src/components/Button.tsx",
          component_name="Button",
          props_mapping={"Variant": "variant", "Size": "size"},
          variants={"primary": {"variant": "primary"}},
          example="<Button variant='primary'>Click</Button>"
    """
    try:
        data = _load_code_connect_data()
        mappings = data.setdefault("mappings", {})
        file_mappings = mappings.setdefault(params.file_key, {})

        # Check if updating existing
        is_update = params.node_id in file_mappings
        timestamp = _get_current_timestamp()

        # Create mapping
        mapping = {
            "component_path": params.component_path,
            "component_name": params.component_name,
            "props_mapping": params.props_mapping,
            "variants": params.variants,
            "example": params.example,
            "updated_at": timestamp
        }

        if is_update:
            # Preserve created_at
            mapping["created_at"] = file_mappings[params.node_id].get("created_at", timestamp)
        else:
            mapping["created_at"] = timestamp

        file_mappings[params.node_id] = mapping
        _save_code_connect_data(data)

        action = "updated" if is_update else "added"
        return json.dumps({
            "status": "success",
            "action": action,
            "file_key": params.file_key,
            "node_id": params.node_id,
            "mapping": mapping,
            "message": f"Code Connect mapping {action} successfully for '{params.component_name}'."
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


@_versioned_tool(
    name="figma_remove_code_connect_map",
    annotations={
        "title": "Remove Code Connect Mapping",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def figma_remove_code_connect_map(params: FigmaCodeConnectRemoveInput) -> str:
    """
    Remove a Code Connect mapping for a Figma component.

    Deletes the mapping between a Figma component and its code implementation.

    Args:
        params: FigmaCodeConnectRemoveInput containing:
            - file_key (str): Figma file key
            - node_id (str): Figma node ID to remove mapping for

    Returns:
        str: JSON formatted result with status

    Examples:
        - Remove mapping: file_key="ABC123", node_id="1:2"
    """
    try:
        data = _load_code_connect_data()
        mappings = data.get("mappings", {})
        file_mappings = mappings.get(params.file_key, {})

        if params.node_id not in file_mappings:
            return json.dumps({
                "status": "not_found",
                "file_key": params.file_key,
                "node_id": params.node_id,
                "message": f"No mapping found for node '{params.node_id}' in file '{params.file_key}'."
            }, indent=2)

        # Remove the mapping
        removed_mapping = file_mappings.pop(params.node_id)

        # Clean up empty file mappings
        if not file_mappings:
            mappings.pop(params.file_key, None)

        _save_code_connect_data(data)

        return json.dumps({
            "status": "success",
            "file_key": params.file_key,
            "node_id": params.node_id,
            "removed_mapping": removed_mapping,
            "message": f"Code Connect mapping removed successfully for '{removed_mapping.get('component_name', 'Unknown')}'."
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


# ============================================================================
# Asset Management Tools
# ============================================================================

@_versioned_tool(
    name="figma_list_assets",
    annotations={
        "title": "List Assets in Figma Design",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_list_assets(params: FigmaListAssetsInput) -> str:
    """
    List all exportable assets in a Figma file or node with smart icon detection.

    Uses intelligent heuristics to detect icon frames (by name pattern like 'mynaui:icon'
    or by size/structure) and treats them as single assets instead of drilling into
    individual vector paths.

    Finds and catalogs:
    - Image fills (photos, illustrations used in design)
    - Icon frames (smart detected by name pattern or size/structure)
    - Raw vector nodes (individual SVG paths, disabled by default)
    - Nodes with export settings configured

    Args:
        params: FigmaListAssetsInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to search within
            - include_images (bool): Include image fills
            - include_icons (bool): Smart detect icon frames (recommended)
            - include_vectors (bool): Include raw vector paths (usually not needed)
            - include_exports (bool): Include nodes with export settings

    Returns:
        str: Cataloged assets in requested format
    """
    try:
        # Get node data
        if params.node_id:
            data = await _make_figma_request(
                f"files/{params.file_key}/nodes",
                params={"ids": params.node_id, "geometry": "paths"}
            )
            nodes = data.get('nodes', {})
            root_node = nodes.get(params.node_id, {}).get('document', {})
        else:
            data = await _make_figma_request(
                f"files/{params.file_key}",
                params={"geometry": "paths"}
            )
            root_node = data.get('document', {})

        if not root_node:
            return "Error: Could not retrieve node data."

        # Collect all assets with smart icon detection
        assets: Dict[str, List] = {
            'images': [],
            'icons': [],
            'vectors': [],
            'exports': []
        }
        _collect_all_assets(
            root_node,
            params.file_key,
            assets,
            include_icons=params.include_icons,
            include_vectors=params.include_vectors,
            include_exports=params.include_exports
        )

        # Filter based on params
        if not params.include_images:
            assets['images'] = []
        if not params.include_icons:
            assets['icons'] = []
        if not params.include_vectors:
            assets['vectors'] = []
        if not params.include_exports:
            assets['exports'] = []

        # Return in requested format
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "file_key": params.file_key,
                "node_id": params.node_id,
                "assets": assets,
                "summary": {
                    "total_images": len(assets['images']),
                    "total_icons": len(assets['icons']),
                    "total_vectors": len(assets['vectors']),
                    "total_exports": len(assets['exports'])
                }
            }, indent=2)

        # Markdown format
        lines = [
            "# Asset Catalog",
            f"**File:** `{params.file_key}`",
        ]
        if params.node_id:
            lines.append(f"**Node:** `{params.node_id}`")
        lines.append("")

        # Summary
        total = len(assets['images']) + len(assets['icons']) + len(assets['vectors']) + len(assets['exports'])
        lines.extend([
            "## Summary",
            f"- **Total Assets:** {total}",
            f"- **Images:** {len(assets['images'])}",
            f"- **Icons:** {len(assets['icons'])}",
            f"- **Raw Vectors:** {len(assets['vectors'])}",
            f"- **Export Configured:** {len(assets['exports'])}",
            ""
        ])

        # Images
        if assets['images']:
            lines.extend(["## 🖼️ Image Fills", ""])
            for img in assets['images'][:20]:  # Limit to 20
                lines.append(f"- **{img['nodeName']}** (`{img['nodeId']}`)")
                lines.append(f"  - imageRef: `{img['imageRef']}`")
                lines.append(f"  - scaleMode: {img['scaleMode']}")
            if len(assets['images']) > 20:
                lines.append(f"- ... and {len(assets['images']) - 20} more")
            lines.append("")

        # Icons (smart detected)
        if assets['icons']:
            lines.extend(["## 🎯 Icons (Smart Detected)", ""])
            lines.append("| Name | Node ID | Type | Size |")
            lines.append("|------|---------|------|------|")
            for icon in assets['icons'][:30]:  # Limit to 30
                size = f"{int(icon['width'])}x{int(icon['height'])}"
                lines.append(f"| {icon['nodeName']} | `{icon['nodeId']}` | {icon['nodeType']} | {size} |")
            if len(assets['icons']) > 30:
                lines.append(f"\n... and {len(assets['icons']) - 30} more icons")
            lines.append("")

        # Raw Vectors (only if explicitly requested)
        if assets['vectors']:
            lines.extend(["## 🎨 Raw Vectors", ""])
            for vec in assets['vectors'][:20]:
                lines.append(f"- **{vec['nodeName']}** (`{vec['nodeId']}`) - {vec['nodeType']}")
            if len(assets['vectors']) > 20:
                lines.append(f"- ... and {len(assets['vectors']) - 20} more")
            lines.append("")

        # Exports
        if assets['exports']:
            lines.extend(["## 📦 Export Configured", ""])
            for exp in assets['exports'][:20]:
                settings = exp['settings']
                formats = [s.get('format', 'PNG') for s in settings]
                lines.append(f"- **{exp['nodeName']}** (`{exp['nodeId']}`) - {', '.join(formats)}")
            if len(assets['exports']) > 20:
                lines.append(f"- ... and {len(assets['exports']) - 20} more")
            lines.append("")

        # Usage hint
        lines.extend([
            "---",
            "**Tip:** Use `figma_get_images` to get actual URLs for image fills,",
            "or `figma_export_assets` to batch export selected assets."
        ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
    name="figma_get_images",
    annotations={
        "title": "Get Image Fill URLs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_get_images(params: FigmaGetImagesInput) -> str:
    """
    Get actual downloadable URLs for image fills in a Figma file.

    Resolves internal imageRef values to real S3 URLs that can be downloaded.
    URLs are valid for 30 days.

    Args:
        params: FigmaGetImagesInput containing:
            - file_key (str): Figma file key
            - node_id (Optional[str]): Specific node to get images from

    Returns:
        str: Image URLs and their references
    """
    try:
        # Get image URLs from Figma API
        data = await _make_figma_request(
            f"files/{params.file_key}/images"
        )

        images = data.get('meta', {}).get('images', {})

        if not images:
            return "No images found in this file. Images must be uploaded to Figma (not external links)."

        # If node_id specified, filter to only images used in that node
        if params.node_id:
            node_data = await _make_figma_request(
                f"files/{params.file_key}/nodes",
                params={"ids": params.node_id}
            )
            nodes = node_data.get('nodes', {})
            root_node = nodes.get(params.node_id, {}).get('document', {})

            if root_node:
                # Collect image refs from node
                assets: Dict[str, List] = {'images': [], 'vectors': [], 'exports': []}
                _collect_all_assets(root_node, params.file_key, assets, include_icons=False, include_vectors=False)
                node_image_refs = {img['imageRef'] for img in assets['images']}

                # Filter to only matching images
                images = {ref: url for ref, url in images.items() if ref in node_image_refs}

        if not images:
            return "No image fills found in the specified node."

        # Create images directory in temp folder
        images_dir = Path(tempfile.gettempdir()) / "figma_images"
        images_dir.mkdir(exist_ok=True)

        lines = [
            "# Image Fill Downloads",
            f"**File:** `{params.file_key}`",
        ]
        if params.node_id:
            lines.append(f"**Node:** `{params.node_id}`")
        lines.extend([
            f"**Total Images:** {len(images)}",
            "",
            "## 📥 Local Files",
            ""
        ])

        # Download and save each image locally
        async with httpx.AsyncClient(timeout=60.0) as client:
            for ref, url in images.items():
                if url:
                    try:
                        response = await client.get(url)
                        response.raise_for_status()

                        # Determine file extension from content type or URL
                        content_type = response.headers.get('content-type', '')
                        if 'png' in content_type or url.endswith('.png'):
                            ext = 'png'
                        elif 'jpeg' in content_type or 'jpg' in content_type or url.endswith('.jpg'):
                            ext = 'jpg'
                        elif 'svg' in content_type or url.endswith('.svg'):
                            ext = 'svg'
                        else:
                            ext = 'png'  # Default to png

                        # Create filename from ref
                        safe_ref = ref.replace(":", "-").replace("/", "-")
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"{params.file_key}_{safe_ref}_{timestamp}.{ext}"
                        filepath = images_dir / filename

                        # Save the image
                        filepath.write_bytes(response.content)

                        lines.append(f"### `{ref}`")
                        lines.append(f"**Saved to:** `{filepath}`")
                        lines.append("")
                    except httpx.HTTPStatusError as e:
                        lines.append(f"### `{ref}`")
                        lines.append(f"⚠️ HTTP error {e.response.status_code}")
                        lines.append("")
                    except httpx.TimeoutException:
                        lines.append(f"### `{ref}`")
                        lines.append(f"⚠️ Download timed out")
                        lines.append("")
                    except OSError as e:
                        lines.append(f"### `{ref}`")
                        lines.append(f"⚠️ File system error - {e.strerror}")
                        lines.append("")
                    except Exception as e:
                        lines.append(f"### `{ref}`")
                        lines.append(f"⚠️ Unexpected error - {type(e).__name__}: {e}")
                        lines.append("")
                else:
                    lines.append(f"### `{ref}`")
                    lines.append("⚠️ URL not available")
                    lines.append("")

        lines.extend([
            "---",
            f"> Images saved to: `{images_dir}`"
        ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@_versioned_tool(
    name="figma_export_assets",
    annotations={
        "title": "Export Assets from Figma",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def figma_export_assets(params: FigmaExportAssetsInput) -> str:
    """
    Batch export assets from Figma nodes.

    Exports multiple nodes as images/SVGs with the specified format and scale.
    For vector nodes, can also generate inline SVG from path data.

    Args:
        params: FigmaExportAssetsInput containing:
            - file_key (str): Figma file key
            - node_ids (List[str]): Node IDs to export
            - format: 'png', 'svg', 'jpg', 'pdf'
            - scale (float): Scale factor (0.01 to 4.0)
            - include_svg_for_vectors (bool): Generate inline SVG for vectors

    Returns:
        str: Export URLs and generated SVGs
    """
    try:
        # Get node data for vector SVG generation
        vector_svgs = {}
        if params.include_svg_for_vectors:
            node_data = await _make_figma_request(
                f"files/{params.file_key}/nodes",
                params={"ids": ",".join(params.node_ids), "geometry": "paths"}
            )
            nodes = node_data.get('nodes', {})

            for node_id in params.node_ids:
                node = nodes.get(node_id, {}).get('document', {})
                if node:
                    vector_paths = _extract_vector_paths(node)
                    if vector_paths:
                        svg = _generate_svg_from_paths(vector_paths, node)
                        if svg:
                            vector_svgs[node_id] = {
                                'name': node.get('name', 'Unnamed'),
                                'svg': svg
                            }

        # Export via Figma Images API
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

        # Create assets directory in temp folder
        assets_dir = Path(tempfile.gettempdir()) / "figma_assets"
        assets_dir.mkdir(exist_ok=True)

        lines = [
            "# Asset Export Results",
            f"**File:** `{params.file_key}`",
            f"**Format:** {params.format.value.upper()}",
            f"**Scale:** {params.scale}x",
            f"**Nodes:** {len(params.node_ids)}",
            "",
            "## 📥 Local Files",
            ""
        ]

        # Download and save each asset locally
        async with httpx.AsyncClient(timeout=60.0) as client:
            for node_id, url in images.items():
                if url:
                    try:
                        response = await client.get(url)
                        response.raise_for_status()

                        # Create filename from node_id
                        safe_node_id = node_id.replace(":", "-")
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"{params.file_key}_{safe_node_id}_{timestamp}.{params.format.value}"
                        filepath = assets_dir / filename

                        # Save the asset
                        filepath.write_bytes(response.content)

                        lines.append(f"- **{node_id}**: `{filepath}`")
                    except httpx.HTTPStatusError as e:
                        lines.append(f"- **{node_id}**: HTTP error {e.response.status_code}")
                    except httpx.TimeoutException:
                        lines.append(f"- **{node_id}**: Download timed out")
                    except OSError as e:
                        lines.append(f"- **{node_id}**: File system error - {e.strerror}")
                    except Exception as e:
                        lines.append(f"- **{node_id}**: Unexpected error - {type(e).__name__}: {e}")
                else:
                    lines.append(f"- **{node_id}**: Export failed")
        lines.append("")

        # Inline SVGs for vectors
        if vector_svgs:
            lines.extend(["## 🎨 Generated SVG (from path data)", ""])
            for node_id, svg_data in vector_svgs.items():
                # Also save SVG to file
                safe_node_id = node_id.replace(":", "-")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                svg_filename = f"{params.file_key}_{safe_node_id}_{timestamp}_generated.svg"
                svg_filepath = assets_dir / svg_filename
                svg_filepath.write_text(svg_data['svg'])

                lines.append(f"### {svg_data['name']} (`{node_id}`)")
                lines.append(f"**Saved to:** `{svg_filepath}`")
                lines.append("```svg")
                lines.append(svg_data['svg'])
                lines.append("```")
                lines.append("")

        lines.extend([
            "---",
            f"> Assets saved to: `{assets_dir}`"
        ])

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
