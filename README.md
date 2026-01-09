# Pixelbyte Figma MCP Server

A powerful MCP (Model Context Protocol) server for Figma API integration. Extract design tokens, generate production-ready code, and capture screenshots directly from your Figma designs.

## Features

- **11 MCP Tools** for complete Figma integration
- **10 Code Frameworks** - React, Vue, Tailwind, CSS, SCSS, SwiftUI, Kotlin
- **Design Token Extraction** - Colors, typography, spacing
- **Nested Children Support** - Full component tree with all styles
- **Screenshot Export** - PNG, SVG, JPG, PDF formats

## Installation

```bash
pip install pixelbyte-figma-mcp
```

## Setup

1. Get your Figma Personal Access Token from [Figma Settings](https://www.figma.com/developers/api#access-tokens)

2. Set the environment variable:
```bash
export FIGMA_ACCESS_TOKEN="your-token-here"
```

3. Add to Claude Code settings (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "pixelbyte-figma-mcp": {
      "command": "pixelbyte-figma-mcp",
      "env": {
        "FIGMA_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `figma_get_file_structure` | Get file hierarchy and node tree |
| `figma_get_node_details` | Get detailed node properties |
| `figma_get_screenshot` | Export nodes as images |
| `figma_get_design_tokens` | Extract colors, fonts, spacing |
| `figma_generate_code` | Generate production-ready code |
| `figma_get_colors` | Extract fill, stroke, shadow colors |
| `figma_get_typography` | Extract font styles |
| `figma_get_spacing` | Extract padding and gap values |
| `figma_get_code_connect_map` | Get Code Connect mappings |
| `figma_add_code_connect_map` | Add/update Code Connect mapping |
| `figma_remove_code_connect_map` | Remove Code Connect mapping |

## Code Generation

Supports 10 frameworks with full nested children and styles:

```python
# React + Tailwind
figma_generate_code(file_key="...", node_id="...", framework="react_tailwind")

# SwiftUI
figma_generate_code(file_key="...", node_id="...", framework="swiftui")

# Kotlin Jetpack Compose
figma_generate_code(file_key="...", node_id="...", framework="kotlin")
```

### Supported Frameworks

| Framework | Output |
|-----------|--------|
| `react` | React + inline styles |
| `react_tailwind` | React + Tailwind CSS |
| `vue` | Vue 3 + scoped CSS |
| `vue_tailwind` | Vue 3 + Tailwind CSS |
| `html_css` | HTML + CSS |
| `tailwind_only` | Tailwind classes only |
| `css` | Pure CSS |
| `scss` | SCSS with variables |
| `swiftui` | iOS SwiftUI Views |
| `kotlin` | Android Jetpack Compose |

## Example Usage

```python
# Get colors from a component
figma_get_colors(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)

# Generate React component
figma_generate_code(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    framework="react_tailwind"
)
```

## Code Connect

Map Figma components to your code implementations for better code generation:

```python
# Add a Code Connect mapping
figma_add_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176",
    component_path="src/components/Button.tsx",
    component_name="Button",
    props_mapping={"Variant": "variant", "Size": "size"},
    variants={"primary": {"variant": "primary"}},
    example="<Button variant='primary'>Click</Button>"
)

# Get all mappings for a file
figma_get_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp"
)

# Remove a mapping
figma_remove_code_connect_map(
    file_key="qyFsYyLyBsutXGGzZ9PLCp",
    node_id="1707:6176"
)
```

**Storage Location:** `~/.config/pixelbyte-figma-mcp/code_connect.json`

**Custom Path:** Set `FIGMA_CODE_CONNECT_PATH` environment variable

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

@PixelByte
