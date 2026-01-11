# 🎨 Pixelbyte Figma MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

A powerful **Model Context Protocol (MCP)** server for seamless Figma API integration. Extract design tokens, generate production-ready code, capture screenshots, and manage Code Connect mappings directly from your Figma designs.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🛠️ **12 MCP Tools** | Complete Figma integration toolkit |
| 💻 **10 Code Frameworks** | React, Vue, Tailwind, CSS, SCSS, SwiftUI, Kotlin |
| 🎨 **Design Tokens** | Extract colors, typography, spacing, effects |
| 🌈 **Gradient Support** | Linear, radial, angular, diamond gradients |
| 🔄 **Transform & Effects** | Rotation, blend modes, shadows, blurs |
| 🌳 **Nested Children** | Full component tree with all styles preserved |
| 📸 **Screenshot Export** | PNG, SVG, JPG, PDF formats with scale control |
| 🔗 **Code Connect** | Map Figma components to code implementations |
| 📦 **Asset Management** | List, export, and download design assets |

---

## 📦 Installation

### From GitHub (Recommended)

```bash
pip install git+https://github.com/Rylaa/pixelbyte-figma-mcp.git
```

### From PyPI

```bash
pip install pixelbyte-figma-mcp
```

### From Source

```bash
git clone https://github.com/Rylaa/pixelbyte-figma-mcp.git
cd pixelbyte-figma-mcp
pip install -e .
```

---

## ⚙️ Setup

### 1. Get Figma Access Token

1. Go to [Figma Account Settings](https://www.figma.com/settings)
2. Scroll to **Personal Access Tokens**
3. Click **Generate new token**
4. Copy the token (you won't see it again!)

### 2. Configure Environment

**Option A: Environment Variable**
```bash
export FIGMA_ACCESS_TOKEN="figd_xxxxxxxxxxxxxxxxxxxxxx"
```

**Option B: .env File**
```bash
# .env
FIGMA_ACCESS_TOKEN=figd_xxxxxxxxxxxxxxxxxxxxxx
```

### 3. Add to Claude Code

Add to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "pixelbyte-figma-mcp": {
      "command": "pixelbyte-figma-mcp",
      "env": {
        "FIGMA_ACCESS_TOKEN": "figd_xxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

### 4. Verify Installation

```bash
# Check if installed correctly
pixelbyte-figma-mcp --help
```

---

## 🛠️ Available Tools

### File & Node Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `figma_get_file_structure` | Get file hierarchy and node tree | `file_key`, `depth` (1-10), `response_format` |
| `figma_get_node_details` | Get detailed node properties | `file_key`, `node_id`, `response_format` |
| `figma_get_screenshot` | Export nodes as images | `file_key`, `node_ids[]`, `format`, `scale` |

### Design Token Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `figma_get_design_tokens` | Extract all design tokens with ready-to-use code | `file_key`, `node_id`, `include_*` flags, `include_generated_code` |
| `figma_get_styles` | Get published styles from file | `file_key`, `include_*` flags |

### Code Generation Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `figma_generate_code` | Generate production-ready code | `file_key`, `node_id`, `framework`, `component_name` |

### Code Connect Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `figma_get_code_connect_map` | Get stored Code Connect mappings | `file_key`, `node_id` (optional) |
| `figma_add_code_connect_map` | Add/update a mapping | `file_key`, `node_id`, `component_path`, `component_name`, `props_mapping`, `variants`, `example` |
| `figma_remove_code_connect_map` | Remove a mapping | `file_key`, `node_id` |

### Asset Management Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `figma_list_assets` | List all exportable assets (images, vectors, exports) | `file_key`, `node_id` (optional), `include_images`, `include_vectors`, `include_exports` |
| `figma_get_images` | Get actual download URLs for image fills | `file_key`, `node_id` (optional) |
| `figma_export_assets` | Batch export nodes with SVG generation | `file_key`, `node_ids[]`, `format`, `scale`, `include_svg_for_vectors` |

---

## 💻 Code Generation

Generate production-ready code for **10 frameworks** with comprehensive style support.

### Supported Styles

| Style Feature | CSS/SCSS | React/Vue | SwiftUI | Kotlin |
|---------------|----------|-----------|---------|--------|
| Solid Colors | ✅ | ✅ | ✅ | ✅ |
| Linear Gradients | ✅ | ✅ | ✅ | ✅ |
| Radial Gradients | ✅ | ✅ | ✅ | ✅ |
| Individual Corner Radii | ✅ | ✅ | ✅ | ✅ |
| Rotation/Transform | ✅ | ✅ | ✅ | ✅ |
| Blend Modes | ✅ | ✅ | ✅ | ✅ |
| Opacity | ✅ | ✅ | ✅ | ✅ |
| Drop Shadows | ✅ | ✅ | ✅ | ✅ |
| Inner Shadows | ✅ | ✅ | - | - |
| Layer Blur | ✅ | ✅ | ✅ | ✅ |
| Background Blur | ✅ | ✅ | - | - |
| Auto Layout | ✅ | ✅ | ✅ | ✅ |

### Supported Frameworks

| Framework | Output | Best For |
|-----------|--------|----------|
| `react` | React + inline styles | Quick prototypes |
| `react_tailwind` | React + Tailwind CSS | Production React apps |
| `vue` | Vue 3 + scoped CSS | Vue.js projects |
| `vue_tailwind` | Vue 3 + Tailwind CSS | Vue + Tailwind projects |
| `html_css` | HTML + CSS | Static sites |
| `tailwind_only` | Tailwind classes only | Copy-paste styling |
| `css` | Pure CSS | Framework-agnostic |
| `scss` | SCSS with variables | Complex styling |
| `swiftui` | iOS SwiftUI Views | iOS development |
| `kotlin` | Android Jetpack Compose | Android development |

### Example Usage

```python
# Generate React + Tailwind component
figma_generate_code(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    framework="react_tailwind",
    component_name="HeroSection"
)

# Generate SwiftUI View
figma_generate_code(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    framework="swiftui"
)

# Generate Android Compose
figma_generate_code(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    framework="kotlin"
)
```

### Generated Code Example

**Input:** A Figma button with gradient, shadow, and rounded corners

**Output (CSS):**
```css
.hero-button {
  width: 200px;
  height: 48px;
  background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
  border-radius: 8px 8px 16px 16px;
  box-shadow: 0px 4px 12px 0px rgba(59, 130, 246, 0.40);
  transform: rotate(0deg);
  opacity: 1;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
}
```

---

## 🎨 Design Token Extraction

Extract design tokens in a structured format with **ready-to-use CSS, SCSS, and Tailwind code**.

### All-in-One Token Extraction

```python
figma_get_design_tokens(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    include_colors=True,
    include_typography=True,
    include_spacing=True,
    include_effects=True,
    include_generated_code=True  # NEW in v2.0!
)
```

**Output:**
```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "figmaFile": "qyFsYyLyBsutXGGzZ9PLCp",
  "tokens": {
    "colors": [
      {
        "name": "Button Background",
        "value": "#3B82F6",
        "hex": "#3B82F6",
        "rgb": "59, 130, 246",
        "hsl": "217, 91%, 60%",
        "contrast": { "white": 3.02, "black": 6.96 }
      }
    ],
    "typography": [...],
    "spacing": [...],
    "shadows": [...],
    "blurs": [...]
  },
  "generated": {
    "css_variables": ":root {\n  --color-button-background: #3B82F6;\n  ...\n}",
    "scss_variables": "$color-button-background: #3B82F6;\n...",
    "tailwind_config": "module.exports = {\n  theme: {\n    extend: {\n      colors: {\n        'button-background': '#3B82F6'\n      }\n    }\n  }\n}"
  }
}
```

### Rich Color Information

Every extracted color now includes:

| Property | Description | Example |
|----------|-------------|---------|
| `hex` | Hexadecimal color | `#3B82F6` |
| `rgb` | RGB values | `59, 130, 246` |
| `hsl` | HSL values | `217, 91%, 60%` |
| `contrast.white` | WCAG contrast ratio vs white | `3.02` |
| `contrast.black` | WCAG contrast ratio vs black | `6.96` |

### Ready-to-Use Generated Code

The `generated` section provides copy-paste ready code:

**CSS Variables:**
```css
:root {
  --color-button-background: #3B82F6;
  --color-card-bg: #FFFFFF;
  --font-inter-16: 16px/24px 'Inter';
  --spacing-card: 24px 24px 24px 24px;
  --shadow-card: 0px 4px 12px rgba(0, 0, 0, 0.1);
}
```

**SCSS Variables:**
```scss
$color-button-background: #3B82F6;
$color-card-bg: #FFFFFF;
$font-inter-size: 16px;
$font-inter-weight: 500;
```

**Tailwind Config:**
```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        'button-background': '#3B82F6',
        'card-bg': '#FFFFFF'
      }
    }
  }
}
```

### Published Styles

```python
figma_get_styles(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    include_fill_styles=True,
    include_text_styles=True,
    include_effect_styles=True
)
```

**Output:**
```json
{
  "fill_styles": [
    {
      "key": "abc123",
      "name": "Primary/500",
      "description": "Primary brand color",
      "fills": [{"type": "SOLID", "color": "#3B82F6"}]
    }
  ],
  "text_styles": [
    {
      "key": "def456",
      "name": "Heading/H1",
      "fontFamily": "Inter",
      "fontSize": 32,
      "fontWeight": 700
    }
  ],
  "effect_styles": [...]
}
```

---

## 🔗 Code Connect

Map Figma components to your actual code implementations for better AI-assisted code generation.

### Why Code Connect?

- 🎯 **Accurate code generation** - AI knows your component paths and props
- 🔄 **Consistent mappings** - Link design to code once, use everywhere
- 📚 **Example snippets** - Provide usage examples for better context

### Add a Mapping

```python
figma_add_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    component_path="src/components/ui/Button.tsx",
    component_name="Button",
    props_mapping={
        "Variant": "variant",      # Figma prop -> Code prop
        "Size": "size",
        "Disabled": "disabled"
    },
    variants={
        "primary": {"variant": "primary", "className": "bg-blue-500"},
        "secondary": {"variant": "secondary", "className": "bg-gray-500"},
        "outline": {"variant": "outline", "className": "border-2"}
    },
    example="<Button variant='primary' size='md'>Click me</Button>"
)
```

### Get Mappings

```python
# Get all mappings for a file
figma_get_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp"
)

# Get specific node mapping
figma_get_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)
```

### Remove a Mapping

```python
figma_remove_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)
```

### Storage Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Storage Path | `~/.config/pixelbyte-figma-mcp/code_connect.json` | Local JSON storage |
| Custom Path | `FIGMA_CODE_CONNECT_PATH` env variable | Override default path |

---

## 📸 Screenshot Export

Export Figma nodes as images in multiple formats.

```python
figma_get_screenshot(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_ids=["1707:6176", "1707:6200"],
    format="png",   # png, svg, jpg, pdf
    scale=2.0       # 0.01 to 4.0
)
```

**Output:**
```json
{
  "images": {
    "1707:6176": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/images/...",
    "1707:6200": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/images/..."
  }
}
```

---

## 🔑 Getting File Key and Node ID

### File Key

From your Figma URL:
```
https://www.figma.com/design/qyFsYyLyBsutXGGzZ9PLCp/My-Design
                              ^^^^^^^^^^^^^^^^^^^^^^
                              This is the file_key
```

### Node ID

1. Select a layer in Figma
2. Right-click → **Copy link**
3. The URL contains `node-id=1707-6176`
4. Use `1707:6176` or `1707-6176` (both work)

---

## 🌍 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIGMA_ACCESS_TOKEN` | ✅ Yes | Figma Personal Access Token |
| `FIGMA_TOKEN` | ⚡ Alternative | Alternative token variable name |
| `FIGMA_CODE_CONNECT_PATH` | ❌ No | Custom Code Connect storage path |

---

## 📋 Requirements

- Python 3.10+
- Figma account with API access
- Personal Access Token

---

## 🆕 What's New in v2.3.x

### v2.3.3 - Bug Fix
- **Fixed KeyError**: Resolved `KeyError: 'value'` in `figma_get_design_tokens` color deduplication
- **Robust dedup keys**: Color deduplication now handles all fill types (solid, gradient, image)

### v2.3.2 - Code Quality Improvements
- **Removed unused functions**: Cleaned up `_color_to_rgb255`, `_color_to_hex`, `_color_to_rgba_str`
- **DRY improvements**: Consolidated inline weight maps to global constants
- **Magic number elimination**: Replaced hardcoded limits with named constants

### v2.3.1 - Network Resilience
- **Retry mechanism**: Added exponential backoff retry for network errors
- **DNS error handling**: Graceful recovery from intermittent DNS resolution failures
- **Improved error messages**: Clearer error descriptions for connection issues

### v2.3.0 - Validator Consolidation
- **Consolidated validators**: Unified validation helpers for cleaner codebase
- **Code organization**: Better structured helper functions

---

## 🆕 What's New in v2.2.0

### 📦 Asset Management System
Three new tools for comprehensive asset handling:

**`figma_list_assets`** - Catalog all exportable assets in your design:
```python
figma_list_assets(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",  # Optional: search within specific node
    include_images=True,
    include_vectors=True,
    include_exports=True
)
```
Returns categorized list of:
- Image fills (photos, illustrations with `imageRef`)
- Vector/icon nodes (SVG exportable shapes)
- Nodes with export settings configured

**`figma_get_images`** - Get actual download URLs for image fills:
```python
figma_get_images(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"  # Optional: filter to specific node
)
```
Resolves internal `imageRef` values to real S3 URLs (valid for 30 days).

**`figma_export_assets`** - Batch export with SVG generation:
```python
figma_export_assets(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_ids=["1:2", "1:3", "1:4"],
    format="png",  # png, svg, jpg, pdf
    scale=2.0,
    include_svg_for_vectors=True  # Generate inline SVG from path data
)
```
Returns download URLs + generated SVG markup for vector nodes.

### 🎨 SVG Generation from Path Data
New helper function generates complete SVG from vector geometry:
- Uses `fillGeometry` and `strokeGeometry` path data
- Preserves fill and stroke colors
- Correct viewBox based on node bounds
- Works with VECTOR, STAR, POLYGON, ELLIPSE, LINE nodes

### 🔧 New Helper Functions
| Function | Description |
|----------|-------------|
| `_resolve_image_urls()` | Convert imageRef to actual S3 URLs |
| `_generate_svg_from_paths()` | Create SVG from vector path geometry |
| `_collect_all_assets()` | Recursively find all assets in node tree |

---

## What's New in v2.1.0

### 🎯 Enhanced Code Generation
- **textCase → CSS**: `UPPER`, `LOWER`, `TITLE` now generate `text-transform` properties
- **Hyperlinks**: Text hyperlinks generate proper `<a>` tags in React/Vue/HTML
- **Line Clamp**: `maxLines` generates `-webkit-line-clamp` CSS for text truncation
- **Paragraph Spacing**: `paragraphSpacing` generates `margin-bottom` on text blocks
- **Flex Grow**: `layoutGrow` generates `flex-grow` for flexible layouts
- **Multiple Fills**: Layered backgrounds now generate comma-separated CSS backgrounds

### 📦 New Extractions
- **Render Bounds**: `absoluteRenderBounds` for actual visual bounds including effects
- **Export Settings**: Format, scale, and SVG options for export configurations
- **Mask Data**: `isMask`, `maskType`, and `clipsContent` for masking behavior
- **Interactions**: Prototype triggers, actions, transitions for hover/click states
- **Vector Paths**: `fillGeometry`, `strokeGeometry` for SVG export
- **Image References**: Image fill refs with API URL hints for resolution

### 🧩 Component Intelligence
- **Variant Properties**: Full variant info for component instances
- **Main Component**: Source component tracking with `mainComponent` details
- **Component Set Name**: Context for variant components

### 🚀 Implementation Hints
AI-friendly guidance automatically generated:
- Layout suggestions (flexbox direction, grid recommendations)
- Responsive hints (breakpoint suggestions, scaling guidance)
- Interaction hints (hover states, click navigation)
- Component hints (variant usage, exposed props)

### ♿ Accessibility Checks
Automatic WCAG compliance warnings:
- **Contrast Issues**: Low contrast text detection with contrast ratios
- **Touch Targets**: Small interactive element warnings (< 44px)
- **Label Warnings**: Missing aria-label on icon-only buttons

---

## What's New in v2.0.0

### ⚠️ Breaking Changes
- **Removed Tools**: `figma_get_colors`, `figma_get_typography`, `figma_get_spacing` have been removed
- **Use Instead**: `figma_get_design_tokens` now provides all these features in one unified tool

### Rich Color Information
- **RGB Values**: Every color now includes RGB string (`59, 130, 246`)
- **HSL Values**: HSL color representation (`217, 91%, 60%`)
- **WCAG Contrast Ratios**: Automatic contrast calculation against white and black backgrounds

### Ready-to-Use Code Generation
- **CSS Variables**: Complete `:root` block with all design tokens
- **SCSS Variables**: SCSS variable definitions for colors, typography, spacing
- **Tailwind Config**: Ready-to-paste Tailwind theme extension

### API Optimizations
- **Faster `figma_get_styles`**: Reduced from 2 API calls to 1 for improved performance
- **Optimized Node Fetching**: Style enrichment now fetches only required nodes

### Previous Features (v1.2.0)
- Gradient support (linear, radial, angular, diamond)
- Transform properties (rotation, scale)
- Advanced effects (layer blur, background blur)
- Multiple shadow support

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Yusuf Demirkoparan** - [@PixelByte](https://github.com/Rylaa)

---

## 🔗 Links

- [GitHub Repository](https://github.com/Rylaa/pixelbyte-figma-mcp)
- [Figma API Documentation](https://www.figma.com/developers/api)
- [Model Context Protocol](https://modelcontextprotocol.io/)
