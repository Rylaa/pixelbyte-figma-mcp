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
from datetime import datetime, timezone
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


class FigmaStylesInput(BaseModel):
    """Input model for published styles retrieval."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(..., description="Figma file key", min_length=10, max_length=50)
    include_fill_styles: bool = Field(default=True, description="Include fill/color styles")
    include_text_styles: bool = Field(default=True, description="Include text/typography styles")
    include_effect_styles: bool = Field(default=True, description="Include effect styles (shadows, blurs)")
    include_grid_styles: bool = Field(default=True, description="Include grid/layout styles")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v: str) -> str:
        if 'figma.com' in v:
            match = re.search(r'figma\.com/(?:design|file)/([a-zA-Z0-9]+)', v)
            if match:
                return match.group(1)
        return v


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

    file_key: str = Field(
        ...,
        description="Figma file key",
        min_length=10,
        max_length=50
    )
    node_id: Optional[str] = Field(
        default=None,
        description="Optional node ID to get specific mapping (returns all if not provided)"
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


class FigmaCodeConnectAddInput(BaseModel):
    """Input model for adding Code Connect mapping."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(
        ...,
        description="Figma file key",
        min_length=10,
        max_length=50
    )
    node_id: str = Field(
        ...,
        description="Figma node ID to map",
        min_length=1
    )
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


class FigmaCodeConnectRemoveInput(BaseModel):
    """Input model for removing Code Connect mapping."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_key: str = Field(
        ...,
        description="Figma file key",
        min_length=10,
        max_length=50
    )
    node_id: str = Field(
        ...,
        description="Figma node ID to remove mapping for",
        min_length=1
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
        base_data['color'] = _rgba_to_hex(color)

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
                stroke_data['color'] = _rgba_to_hex(stroke.get('color', {}))
            elif stroke_type.startswith('GRADIENT_'):
                stroke_data['gradient'] = {
                    'type': stroke_type.replace('GRADIENT_', ''),
                    'stops': _extract_gradient_stops(stroke.get('gradientStops', [])),
                    'handlePositions': stroke.get('gradientHandlePositions', [])
                }

            stroke_colors.append(stroke_data)

    return {
        'colors': stroke_colors,
        'weight': node.get('strokeWeight', 1),
        'align': node.get('strokeAlign', 'INSIDE'),
        'cap': node.get('strokeCap', 'NONE'),
        'join': node.get('strokeJoin', 'MITER'),
        'miterLimit': node.get('strokeMiterLimit', 4),
        'dashes': node.get('strokeDashes', []),
        'dashCap': node.get('strokeDashCap', 'NONE')
    }


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
    """Extract transform properties."""
    transform = {
        'rotation': node.get('rotation', 0),
        'preserveRatio': node.get('preserveRatio', False)
    }

    if 'relativeTransform' in node:
        transform['relativeTransform'] = node['relativeTransform']

    return transform


def _extract_component_info(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract component/instance information."""
    node_type = node.get('type', '')

    if node_type == 'INSTANCE':
        return {
            'isInstance': True,
            'componentId': node.get('componentId'),
            'componentProperties': node.get('componentProperties', {}),
            'overrides': node.get('overrides', []),
            'exposedInstances': node.get('exposedInstances', [])
        }
    elif node_type == 'COMPONENT':
        return {
            'isComponent': True,
            'componentPropertyDefinitions': node.get('componentPropertyDefinitions', {}),
            'componentSetId': node.get('componentSetId')
        }
    elif node_type == 'COMPONENT_SET':
        return {
            'isComponentSet': True,
            'componentPropertyDefinitions': node.get('componentPropertyDefinitions', {})
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
            shadows.append({
                'type': effect_type,
                'color': _rgba_to_hex(color),
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

    # relativeTransform matrix (skew, scale)
    relative_transform = node.get('relativeTransform')
    if relative_transform and len(relative_transform) >= 2:
        # relativeTransform is [[a, b, tx], [c, d, ty]]
        a = relative_transform[0][0] if len(relative_transform[0]) > 0 else 1
        b = relative_transform[0][1] if len(relative_transform[0]) > 1 else 0
        c = relative_transform[1][0] if len(relative_transform[1]) > 0 else 0
        d = relative_transform[1][1] if len(relative_transform[1]) > 1 else 1

        # Check for scale (not just rotation which we already handled)
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


def _get_background_css(node: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract background CSS (color or gradient) from node fills.

    Returns:
        tuple: (background_value, background_type) where type is 'color' or 'gradient'
    """
    fills = node.get('fills', [])
    if not fills:
        return None, None

    for fill in fills:
        if not fill.get('visible', True):
            continue

        fill_type = fill.get('type', '')

        if fill_type == 'SOLID':
            color = fill.get('color', {})
            opacity = fill.get('opacity', 1)
            hex_color = _rgba_to_hex(color)

            if opacity < 1:
                r = int(color.get('r', 0) * 255)
                g = int(color.get('g', 0) * 255)
                b = int(color.get('b', 0) * 255)
                return f"rgba({r}, {g}, {b}, {opacity:.2f})", 'color'

            return hex_color, 'color'

        elif 'GRADIENT' in fill_type:
            gradient_css = _gradient_to_css(fill)
            if gradient_css:
                return gradient_css, 'gradient'

        elif fill_type == 'IMAGE':
            # Return placeholder for image
            image_ref = fill.get('imageRef', '')
            return f"/* Image: {image_ref} */", 'image'

    return None, None


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
    """Recursively generate Vue template code for nested children with enhanced styles."""
    lines = []
    prefix = ' ' * indent
    node_type = node.get('type', '')
    name = node.get('name', 'Unknown')

    bbox = node.get('absoluteBoundingBox', {})
    width = int(bbox.get('width', 0))
    height = int(bbox.get('height', 0))

    # Fills (with gradient support)
    fills = node.get('fills', [])
    bg_value, bg_type = _get_background_css(node)

    # Strokes
    stroke_data = _extract_stroke_data(node)
    stroke_color = ''
    stroke_weight = stroke_data['weight'] if stroke_data else 0
    if stroke_data and stroke_data['colors']:
        first_stroke = stroke_data['colors'][0]
        if first_stroke.get('type') == 'SOLID':
            stroke_color = first_stroke.get('color', '')

    # Corner radius (with individual corners)
    corner_radius_css = _corner_radii_to_css(node)

    # Transform
    transform_css = _transform_to_css(node)

    # Blend mode and opacity
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_mode_css = _blend_mode_to_css(blend_mode)
    opacity = node.get('opacity', 1)

    # Layout
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
            inline_styles = []

            if width:
                classes.append(f'w-[{width}px]')
            if height:
                classes.append(f'h-[{height}px]')

            # Background
            if bg_value and bg_type:
                if bg_type == 'color':
                    classes.append(f'bg-[{bg_value}]')
                elif bg_type == 'gradient':
                    inline_styles.append(f"background: {bg_value}")

            # Corner radius
            if corner_radius_css:
                classes.append(f'rounded-[{corner_radius_css}]')

            # Strokes
            if stroke_color and stroke_weight:
                classes.append(f'border-[{stroke_weight}px]')
                classes.append(f'border-[{stroke_color}]')

            # Transform
            if transform_css:
                inline_styles.append(f"transform: {transform_css}")

            # Blend mode
            if blend_mode_css:
                classes.append(f'mix-blend-{blend_mode_css}')

            # Opacity
            if opacity < 1:
                classes.append(f'opacity-[{opacity}]')

            # Layout
            if layout_mode:
                classes.append('flex')
                classes.append('flex-col' if layout_mode == 'VERTICAL' else 'flex-row')
                if gap:
                    classes.append(f'gap-[{gap}px]')

            # Padding
            if padding_top:
                classes.append(f'pt-[{padding_top}px]')
            if padding_right:
                classes.append(f'pr-[{padding_right}px]')
            if padding_bottom:
                classes.append(f'pb-[{padding_bottom}px]')
            if padding_left:
                classes.append(f'pl-[{padding_left}px]')

            class_str = ' '.join(filter(None, classes))

            if inline_styles:
                style_str = '; '.join(inline_styles)
                lines.append(f'{prefix}<div class="{class_str}" style="{style_str}">')
            else:
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
    """Generate pure CSS code from Figma node with enhanced style support."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 'auto')
    height = bbox.get('height', 'auto')

    # Background (with gradient support)
    bg_value, bg_type = _get_background_css(node)
    bg_css = ''
    if bg_value and bg_type:
        if bg_type == 'color':
            bg_css = f"background-color: {bg_value};"
        elif bg_type == 'gradient':
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

    css_content = '\n  '.join(css_lines)

    code = f'''.{component_name.lower()} {{
  {css_content}
}}'''
    return code


def _generate_scss_code(node: Dict[str, Any], component_name: str) -> str:
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

    styles = '\n  '.join(styles_list)

    code = f'''{variables}

.{component_name.lower().replace(" ", "-")} {{
  {styles}
}}'''
    return code


def _generate_swiftui_code(node: Dict[str, Any], component_name: str) -> str:
    """Generate SwiftUI code from Figma node with comprehensive style support."""
    bbox = node.get('absoluteBoundingBox', {})
    width = bbox.get('width', 100)
    height = bbox.get('height', 100)

    # Background (with gradient support)
    fills = node.get('fills', [])
    bg_code = ''
    gradient_def = ''

    for fill in fills:
        if not fill.get('visible', True):
            continue
        fill_type = fill.get('type', '')

        if fill_type == 'SOLID':
            color = fill.get('color', {})
            r = color.get('r', 0)
            g = color.get('g', 0)
            b = color.get('b', 0)
            a = fill.get('opacity', color.get('a', 1))
            bg_code = f"Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}, opacity: {a:.2f})"
            break

        elif fill_type == 'GRADIENT_LINEAR':
            stops = fill.get('gradientStops', [])
            if stops:
                gradient_stops = []
                for stop in stops:
                    pos = stop.get('position', 0)
                    c = stop.get('color', {})
                    gradient_stops.append(
                        f"Gradient.Stop(color: Color(red: {c.get('r', 0):.3f}, green: {c.get('g', 0):.3f}, blue: {c.get('b', 0):.3f}), location: {pos:.2f})"
                    )
                gradient_def = f'''
    let gradient = LinearGradient(
        stops: [
            {(",{chr(10)}            ").join(gradient_stops)}
        ],
        startPoint: .leading,
        endPoint: .trailing
    )'''
                bg_code = 'gradient'
            break

        elif fill_type == 'GRADIENT_RADIAL':
            stops = fill.get('gradientStops', [])
            if stops:
                gradient_stops = []
                for stop in stops:
                    pos = stop.get('position', 0)
                    c = stop.get('color', {})
                    gradient_stops.append(
                        f"Gradient.Stop(color: Color(red: {c.get('r', 0):.3f}, green: {c.get('g', 0):.3f}, blue: {c.get('b', 0):.3f}), location: {pos:.2f})"
                    )
                gradient_def = f'''
    let gradient = RadialGradient(
        stops: [
            {(",{chr(10)}            ").join(gradient_stops)}
        ],
        center: .center,
        startRadius: 0,
        endRadius: {max(width, height) / 2}
    )'''
                bg_code = 'gradient'
            break

    # Individual corner radii
    corner_radii = node.get('rectangleCornerRadii', [])
    corner_radius = node.get('cornerRadius', 0)
    corner_code = ''

    if corner_radii and len(corner_radii) == 4:
        tl, tr, br, bl = corner_radii
        if tl == tr == br == bl:
            corner_code = f'.cornerRadius({tl})' if tl > 0 else ''
        else:
            # SwiftUI doesn't support individual corners directly, use clipShape with custom shape
            corner_code = f'.clipShape(RoundedCorner(topLeft: {tl}, topRight: {tr}, bottomRight: {br}, bottomLeft: {bl}))'
    elif corner_radius:
        corner_code = f'.cornerRadius({corner_radius})'

    # Rotation
    rotation = node.get('rotation', 0)
    rotation_code = f'.rotationEffect(.degrees({rotation:.1f}))' if rotation != 0 else ''

    # Opacity
    opacity = node.get('opacity', 1)
    opacity_code = f'.opacity({opacity:.2f})' if opacity < 1 else ''

    # Blend mode
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_map = {
        'MULTIPLY': '.multiply', 'SCREEN': '.screen', 'OVERLAY': '.overlay',
        'DARKEN': '.darken', 'LIGHTEN': '.lighten', 'COLOR_DODGE': '.colorDodge',
        'COLOR_BURN': '.colorBurn', 'SOFT_LIGHT': '.softLight', 'HARD_LIGHT': '.hardLight',
        'DIFFERENCE': '.difference', 'EXCLUSION': '.exclusion'
    }
    blend_code = f'.blendMode({blend_map[blend_mode]})' if blend_mode in blend_map else ''

    # Effects (shadows and blurs)
    effects = node.get('effects', [])
    shadow_codes = []
    blur_code = ''

    for effect in effects:
        if not effect.get('visible', True):
            continue
        effect_type = effect.get('type', '')

        if effect_type == 'DROP_SHADOW':
            color = effect.get('color', {})
            offset_x = effect.get('offset', {}).get('x', 0)
            offset_y = effect.get('offset', {}).get('y', 0)
            blur = effect.get('radius', 0)
            r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
            a = color.get('a', 0.25)
            shadow_codes.append(
                f'.shadow(color: Color(red: {r:.3f}, green: {g:.3f}, blue: {b:.3f}, opacity: {a:.2f}), radius: {blur}, x: {offset_x}, y: {offset_y})'
            )
        elif effect_type == 'LAYER_BLUR':
            blur_code = f'.blur(radius: {effect.get("radius", 0)})'

    layout_mode = node.get('layoutMode')
    gap = node.get('itemSpacing', 0)
    padding_top = node.get('paddingTop', 0)
    padding_right = node.get('paddingRight', 0)
    padding_bottom = node.get('paddingBottom', 0)
    padding_left = node.get('paddingLeft', 0)

    # Advanced alignment
    primary_align = node.get('primaryAxisAlignItems', 'MIN')
    counter_align = node.get('counterAxisAlignItems', 'MIN')

    # Determine container type and alignment
    container = 'VStack' if layout_mode == 'VERTICAL' else 'HStack' if layout_mode == 'HORIZONTAL' else 'ZStack'

    h_align_map = {'MIN': '.leading', 'CENTER': '.center', 'MAX': '.trailing'}
    v_align_map = {'MIN': '.top', 'CENTER': '.center', 'MAX': '.bottom'}

    if layout_mode == 'VERTICAL':
        alignment = h_align_map.get(counter_align, '.center')
    else:
        alignment = v_align_map.get(counter_align, '.center')

    spacing_param = f"alignment: {alignment}, spacing: {gap}" if gap else f"alignment: {alignment}"

    # Generate children
    children_code = _generate_swiftui_children(node.get('children', []))

    # Build modifiers
    modifiers = []
    modifiers.append(f'.frame(width: {int(width)}, height: {int(height)})')
    if bg_code:
        modifiers.append(f'.background({bg_code})')
    if corner_code:
        modifiers.append(corner_code)
    modifiers.extend(shadow_codes)
    if blur_code:
        modifiers.append(blur_code)
    if rotation_code:
        modifiers.append(rotation_code)
    if opacity_code:
        modifiers.append(opacity_code)
    if blend_code:
        modifiers.append(blend_code)
    if padding_top or padding_right or padding_bottom or padding_left:
        modifiers.append(f'.padding(EdgeInsets(top: {padding_top}, leading: {padding_left}, bottom: {padding_bottom}, trailing: {padding_right}))')

    modifiers_str = '\n        '.join(modifiers)

    # Custom RoundedCorner shape if needed
    rounded_corner_shape = ''
    if 'RoundedCorner' in corner_code:
        rounded_corner_shape = '''

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

    code = f'''import SwiftUI

struct {component_name}: View {{{gradient_def}
    var body: some View {{
        {container}({spacing_param}) {{
{children_code if children_code else '            // Content'}
        }}
        {modifiers_str}
    }}
}}

#Preview {{
    {component_name}()
}}{rounded_corner_shape}
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
    children_code = _generate_kotlin_children(node.get('children', []))

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
            {modifiers_str}{f''',
        {arrangement}''' if arrangement else ''}
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

    # Fills (with gradient support)
    fills = node.get('fills', [])
    bg_value, bg_type = _get_background_css(node)

    # Strokes (comprehensive)
    stroke_data = _extract_stroke_data(node)
    stroke_color = ''
    stroke_weight = stroke_data['weight'] if stroke_data else 0
    stroke_align = stroke_data['align'] if stroke_data else 'INSIDE'
    if stroke_data and stroke_data['colors']:
        first_stroke = stroke_data['colors'][0]
        if first_stroke.get('type') == 'SOLID':
            stroke_color = first_stroke.get('color', '')

    # Effects (shadows and blurs)
    effects_data = _extract_effects_data(node)
    shadow_css = ''
    blur_css = ''
    if effects_data['shadows']:
        shadow_parts = []
        for shadow in effects_data['shadows']:
            offset = shadow.get('offset', {'x': 0, 'y': 0})
            shadow_parts.append(
                f"{int(offset.get('x', 0))}px {int(offset.get('y', 0))}px {int(shadow.get('radius', 0))}px {int(shadow.get('spread', 0))}px {shadow.get('color', '#000')}"
            )
        shadow_css = ', '.join(shadow_parts)
    if effects_data['blurs']:
        for blur in effects_data['blurs']:
            if blur.get('type') == 'LAYER_BLUR':
                blur_css = f"blur({int(blur.get('radius', 0))}px)"
            elif blur.get('type') == 'BACKGROUND_BLUR':
                blur_css = f"blur({int(blur.get('radius', 0))}px)"

    # Corner radius (with individual corners support)
    corner_radius_css = _corner_radii_to_css(node)

    # Transform (rotation, scale)
    transform_css = _transform_to_css(node)

    # Blend mode
    blend_mode = node.get('blendMode', 'PASS_THROUGH')
    blend_mode_css = _blend_mode_to_css(blend_mode)

    # Opacity
    opacity = node.get('opacity', 1)

    # Layout
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
            if bg_value and bg_type == 'color':
                classes.append(f'bg-[{bg_value}]')
            class_str = ' '.join(filter(None, classes))
            lines.append(f'{prefix}{{/* Icon: {name} */}}')
            lines.append(f'{prefix}<div className="{class_str}" />')
        else:
            styles = []
            if width:
                styles.append(f"width: '{width}px'")
            if height:
                styles.append(f"height: '{height}px'")
            if bg_value and bg_type == 'color':
                styles.append(f"backgroundColor: '{bg_value}'")
            style_str = ', '.join(styles) if styles else "width: '0px'"
            lines.append(f'{prefix}{{/* Icon: {name} */}}')
            lines.append(f'{prefix}<div style={{{{ {style_str} }}}} />')

    else:
        # Container element (FRAME, GROUP, COMPONENT, INSTANCE, RECTANGLE, etc.)
        if use_tailwind:
            classes = []
            inline_styles = []  # For properties that can't be expressed in Tailwind alone

            if width:
                classes.append(f'w-[{width}px]')
            if height:
                classes.append(f'h-[{height}px]')

            # Background (solid color or gradient)
            if bg_value and bg_type:
                if bg_type == 'color':
                    classes.append(f'bg-[{bg_value}]')
                elif bg_type == 'gradient':
                    # Gradients need inline style in Tailwind
                    inline_styles.append(f"background: '{bg_value}'")
                elif bg_type == 'image':
                    # Image placeholder
                    inline_styles.append(f"/* {bg_value} */")

            # Corner radius (with individual corners)
            if corner_radius_css:
                classes.append(f'rounded-[{corner_radius_css}]')

            # Strokes
            if stroke_color and stroke_weight:
                classes.append(f'border-[{stroke_weight}px]')
                classes.append(f'border-[{stroke_color}]')
                # Border position (only INSIDE is default in CSS)
                if stroke_align == 'OUTSIDE':
                    inline_styles.append("boxSizing: 'content-box'")

            # Shadows
            if shadow_css:
                classes.append(f'shadow-[{shadow_css}]')

            # Blur filter
            if blur_css:
                inline_styles.append(f"filter: '{blur_css}'")

            # Transform (rotation, scale)
            if transform_css:
                inline_styles.append(f"transform: '{transform_css}'")

            # Blend mode
            if blend_mode_css:
                classes.append(f'mix-blend-{blend_mode_css}')

            # Opacity
            if opacity < 1:
                classes.append(f'opacity-[{opacity}]')

            # Layout
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

            # Padding
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

            # Combine className and style if needed
            if inline_styles:
                style_str = ', '.join(inline_styles)
                lines.append(f'{prefix}<div className="{class_str}" style={{{{ {style_str} }}}}>')
            else:
                lines.append(f'{prefix}<div className="{class_str}">')
        else:
            styles = []
            if width:
                styles.append(f"width: '{width}px'")
            if height:
                styles.append(f"height: '{height}px'")

            # Background (solid color or gradient)
            if bg_value and bg_type:
                if bg_type == 'color':
                    styles.append(f"backgroundColor: '{bg_value}'")
                elif bg_type == 'gradient':
                    styles.append(f"background: '{bg_value}'")
                elif bg_type == 'image':
                    styles.append(f"/* {bg_value} */")

            # Corner radius (with individual corners)
            if corner_radius_css:
                styles.append(f"borderRadius: '{corner_radius_css}'")

            # Strokes
            if stroke_color and stroke_weight:
                styles.append(f"border: '{stroke_weight}px solid {stroke_color}'")
                if stroke_align == 'OUTSIDE':
                    styles.append("boxSizing: 'content-box'")

            # Shadows
            if shadow_css:
                styles.append(f"boxShadow: '{shadow_css}'")

            # Blur filter
            if blur_css:
                styles.append(f"filter: '{blur_css}'")

            # Transform (rotation, scale)
            if transform_css:
                styles.append(f"transform: '{transform_css}'")

            # Blend mode
            if blend_mode_css:
                styles.append(f"mixBlendMode: '{blend_mode_css}'")

            # Opacity
            if opacity < 1:
                styles.append(f"opacity: {opacity}")

            # Layout
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

            # Padding
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

        # Bounds
        bbox = node.get('absoluteBoundingBox', {})
        if bbox:
            node_details['bounds'] = {
                'width': round(bbox.get('width', 0), 2),
                'height': round(bbox.get('height', 0), 2),
                'x': round(bbox.get('x', 0), 2),
                'y': round(bbox.get('y', 0), 2)
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

        # Transform
        transform = _extract_transform(node)
        if transform.get('rotation') or transform.get('preserveRatio'):
            node_details['transform'] = transform

        # Clip content
        if 'clipsContent' in node:
            node_details['clipsContent'] = node['clipsContent']

        # Component/Instance info
        component_info = _extract_component_info(node)
        if component_info:
            node_details['component'] = component_info

        # Bound variables
        bound_variables = _extract_bound_variables(node)
        if bound_variables:
            node_details['boundVariables'] = bound_variables

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

        # Children count
        children = node.get('children', [])
        if children:
            node_details['childrenCount'] = len(children)

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
                    lines.append(f"- **Solid:** {fill.get('color')} (opacity: {fill.get('opacity', 1):.2f})")
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
            lines.append("")

        # Strokes
        if 'strokes' in node_details:
            s = node_details['strokes']
            lines.append("## Strokes")
            lines.append(f"- **Weight:** {s['weight']}px")
            lines.append(f"- **Align:** {s['align']}")
            lines.append(f"- **Cap:** {s['cap']}, **Join:** {s['join']}")
            if s.get('dashes'):
                lines.append(f"- **Dashes:** {s['dashes']}")
            for color in s.get('colors', []):
                if color.get('type') == 'SOLID':
                    lines.append(f"- **Color:** {color.get('color')}")
                elif color.get('type', '').startswith('GRADIENT_'):
                    lines.append(f"- **Gradient stroke**")
            lines.append("")

        # Corner radius
        if 'cornerRadius' in node_details:
            cr = node_details['cornerRadius']
            if cr.get('isUniform'):
                lines.append(f"## Border Radius: {cr['topLeft']}px\n")
            else:
                lines.extend([
                    "## Border Radius",
                    f"- **Top Left:** {cr['topLeft']}px",
                    f"- **Top Right:** {cr['topRight']}px",
                    f"- **Bottom Right:** {cr['bottomRight']}px",
                    f"- **Bottom Left:** {cr['bottomLeft']}px",
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
            if node_details['effects'].get('blurs'):
                for blur in node_details['effects']['blurs']:
                    lines.append(f"- **{blur['type']}:** {blur['radius']}px")
            lines.append("")

        # Auto-layout
        if 'autoLayout' in node_details:
            al = node_details['autoLayout']
            lines.extend([
                "## Auto Layout",
                f"- **Direction:** {al['mode']}",
                f"- **Gap:** {al['gap']}px",
                f"- **Padding:** T:{al['padding']['top']} R:{al['padding']['right']} B:{al['padding']['bottom']} L:{al['padding']['left']}",
                f"- **Primary Align:** {al['primaryAxisAlign']}",
                f"- **Counter Align:** {al['counterAxisAlign']}",
                f"- **Primary Sizing:** {al['primaryAxisSizing']}",
                f"- **Counter Sizing:** {al['counterAxisSizing']}",
            ])
            if al.get('layoutWrap') != 'NO_WRAP':
                lines.append(f"- **Wrap:** {al['layoutWrap']}")
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
            lines.append("")

        # Children count
        if 'childrenCount' in node_details:
            lines.append(f"**Children:** {node_details['childrenCount']} child node(s)")

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

        # Categorize styles
        fill_styles = []
        text_styles = []
        effect_styles = []
        grid_styles = []

        for style in styles:
            style_type = style.get('style_type', '')
            style_data = {
                'key': style.get('key', ''),
                'name': style.get('name', ''),
                'description': style.get('description', ''),
                'node_id': style.get('node_id', ''),
                'created_at': style.get('created_at', ''),
                'updated_at': style.get('updated_at', ''),
                'sort_position': style.get('sort_position', '')
            }

            if style_type == 'FILL' and params.include_fill_styles:
                fill_styles.append(style_data)
            elif style_type == 'TEXT' and params.include_text_styles:
                text_styles.append(style_data)
            elif style_type == 'EFFECT' and params.include_effect_styles:
                effect_styles.append(style_data)
            elif style_type == 'GRID' and params.include_grid_styles:
                grid_styles.append(style_data)

        # Now fetch full file to get style details
        file_data = await _make_figma_request(f"files/{params.file_key}")

        # Extract style definitions from document styles
        doc_styles = file_data.get('styles', {})

        # Enrich styles with actual values
        def enrich_style(style_data: Dict, doc_styles: Dict, file_data: Dict) -> Dict:
            node_id = style_data.get('node_id', '')
            if node_id and node_id in doc_styles:
                style_info = doc_styles[node_id]
                style_data['styleType'] = style_info.get('styleType', '')

            # Try to get the actual node to extract values
            node = _find_node_by_id(file_data.get('document', {}), node_id)
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
        fill_styles = [enrich_style(s, doc_styles, file_data) for s in fill_styles]
        text_styles = [enrich_style(s, doc_styles, file_data) for s in text_styles]
        effect_styles = [enrich_style(s, doc_styles, file_data) for s in effect_styles]
        grid_styles = [enrich_style(s, doc_styles, file_data) for s in grid_styles]

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
# Code Connect Tools
# ============================================================================

@mcp.tool(
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


@mcp.tool(
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


@mcp.tool(
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
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
