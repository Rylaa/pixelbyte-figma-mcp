# Figma MCP Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical KeyError bug and improve code quality in pixelbyte-figma-mcp

**Architecture:** Direct fixes to figma_mcp.py with minimal changes, following existing code patterns

**Tech Stack:** Python 3.11+, httpx, Pydantic, asyncio

---

## Task 1: Fix Critical KeyError in figma_get_images

**Files:**
- Modify: `figma_mcp.py:5935-5936`

**Step 1: Locate the bug**

```bash
grep -n "assets: Dict\[str, List\] = {'images" figma_mcp.py
```

Expected: Line 5935 shows dict without 'icons' key

**Step 2: Apply the fix**

Change line 5936 to pass `include_icons=False`:

```python
# Before (BUGGY)
assets: Dict[str, List] = {'images': [], 'vectors': [], 'exports': []}
_collect_all_assets(root_node, params.file_key, assets)

# After (FIXED)
assets: Dict[str, List] = {'images': [], 'vectors': [], 'exports': []}
_collect_all_assets(root_node, params.file_key, assets, include_icons=False, include_vectors=False)
```

**Step 3: Verify fix**

```bash
python -c "
assets = {'images': [], 'vectors': [], 'exports': []}
# Simulating the function call with include_icons=False
# Should not try to access assets['icons']
print('Fix verified: No KeyError')
"
```

Expected: "Fix verified: No KeyError"

**Step 4: Commit**

```bash
git add figma_mcp.py
git commit -m "fix: prevent KeyError in figma_get_images by disabling icon collection"
```

---

## Task 2: Add Timestamp Microseconds to Prevent Collisions

**Files:**
- Modify: `figma_mcp.py` (multiple locations)

**Step 1: Find all timestamp usages**

```bash
grep -n "strftime.*%H%M%S" figma_mcp.py
```

**Step 2: Update timestamp format**

Change all occurrences from:
```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
```

To:
```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
```

**Step 3: Verify changes**

```bash
python -c "
from datetime import datetime
ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
print(f'Timestamp with microseconds: {ts}')
assert len(ts) == 22, 'Should be 22 chars'
print('Timestamp format verified')
"
```

Expected: 22-character timestamp with microseconds

**Step 4: Commit**

```bash
git add figma_mcp.py
git commit -m "fix: add microseconds to timestamps to prevent filename collisions"
```

---

## Task 3: Improve Exception Handling Specificity

**Files:**
- Modify: `figma_mcp.py` (download error handlers)

**Step 1: Find generic exception handlers**

```bash
grep -n "except Exception as download_err" figma_mcp.py
```

**Step 2: Replace with specific handlers**

For each download block, change:

```python
# Before
except Exception as download_err:
    lines.append(f"- **{node_id}**: Failed to download - {download_err}")

# After
except httpx.HTTPStatusError as e:
    lines.append(f"- **{node_id}**: HTTP error {e.response.status_code}")
except httpx.TimeoutException:
    lines.append(f"- **{node_id}**: Download timed out")
except OSError as e:
    lines.append(f"- **{node_id}**: File system error - {e.strerror}")
except Exception as e:
    lines.append(f"- **{node_id}**: Unexpected error - {type(e).__name__}: {e}")
```

**Step 3: Verify syntax**

```bash
python -m py_compile figma_mcp.py && echo "Syntax OK"
```

Expected: "Syntax OK"

**Step 4: Commit**

```bash
git add figma_mcp.py
git commit -m "fix: improve exception handling specificity in download functions"
```

---

## Task 4: Update Version Number

**Files:**
- Modify: `pyproject.toml`

**Step 1: Read current version**

```bash
grep "version = " pyproject.toml
```

**Step 2: Bump to v2.3.7**

```toml
version = "2.3.7"
```

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 2.3.7"
```

---

## Task 5: Update README Changelog

**Files:**
- Modify: `README.md`

**Step 1: Add changelog entry**

Add to changelog section:

```markdown
### v2.3.7
- fix: prevent KeyError in figma_get_images by disabling icon collection
- fix: add microseconds to timestamps to prevent filename collisions
- fix: improve exception handling specificity in download functions
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add v2.3.7 changelog"
```

---

## Verification Checklist

After completing all tasks:

- [ ] `python -m py_compile figma_mcp.py` passes
- [ ] Version is 2.3.7 in pyproject.toml
- [ ] All 5 commits are in git log
- [ ] No pending changes (`git status` clean)
