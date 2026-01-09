# 🎨 Pixelbyte Figma MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

A powerful **Model Context Protocol (MCP)** server for seamless Figma API integration. Extract design tokens, generate production-ready code, capture screenshots, and manage Code Connect mappings directly from your Figma designs.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🛠️ **11 MCP Tools** | Complete Figma integration toolkit |
| 💻 **10 Code Frameworks** | React, Vue, Tailwind, CSS, SCSS, SwiftUI, Kotlin |
| 🎨 **Design Tokens** | Extract colors, typography, spacing, effects |
| 🌳 **Nested Children** | Full component tree with all styles preserved |
| 📸 **Screenshot Export** | PNG, SVG, JPG, PDF formats with scale control |
| 🔗 **Code Connect** | Map Figma components to code implementations |

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
| `figma_get_design_tokens` | Extract all design tokens | `file_key`, `node_id`, `include_*` flags |
| `figma_get_colors` | Extract fill, stroke, shadow colors | `file_key`, `node_id`, `include_*` flags |
| `figma_get_typography` | Extract font styles | `file_key`, `node_id` |
| `figma_get_spacing` | Extract padding and gap values | `file_key`, `node_id` |

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

---

## 💻 Code Generation

Generate production-ready code for **10 frameworks** with full nested children and styles.

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

---

## 🎨 Design Token Extraction

Extract design tokens in a structured format for your design system.

### Colors

```python
figma_get_colors(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    include_fills=True,
    include_strokes=True,
    include_shadows=True
)
```

**Output:**
```json
{
  "fills": [
    {"hex": "#3B82F6", "rgba": "rgba(59, 130, 246, 1)", "name": "primary-500"}
  ],
  "strokes": [...],
  "shadows": [...]
}
```

### Typography

```python
figma_get_typography(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)
```

**Output:**
```json
{
  "typography": [
    {
      "fontFamily": "Inter",
      "fontSize": 16,
      "fontWeight": 500,
      "lineHeight": 24,
      "letterSpacing": 0
    }
  ],
  "summary": {
    "fontFamilies": ["Inter", "Roboto"],
    "fontSizes": [12, 14, 16, 18, 24, 32],
    "fontWeights": [400, 500, 600, 700]
  }
}
```

### Spacing

```python
figma_get_spacing(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)
```

**Output:**
```json
{
  "spacing": [
    {
      "name": "Card",
      "padding": {"top": 24, "right": 24, "bottom": 24, "left": 24},
      "gap": 16,
      "layoutMode": "VERTICAL"
    }
  ],
  "summary": {
    "uniquePaddingValues": [8, 12, 16, 24, 32],
    "uniqueGapValues": [8, 12, 16, 24]
  }
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
