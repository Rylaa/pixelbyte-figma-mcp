#!/usr/bin/env python3
"""Test mobile scroll detection fix"""

# Mock Figma API response for node 144-3313
mock_node = {
    'id': '144:3313',
    'name': 'iPhone 13 & 14 - 54',
    'type': 'FRAME',
    'absoluteBoundingBox': {
        'x': -471,
        'y': 2863,
        'width': 390,
        'height': 1248
    },
    'fills': [{'type': 'SOLID', 'color': {'r': 0, 'g': 0, 'b': 0}, 'visible': True}],
    'children': [
        {
            'id': '144:3314',
            'name': 'Frame 2121315765',
            'type': 'FRAME',
            'absoluteBoundingBox': {'x': -471, 'y': 3434, 'width': 394, 'height': 106},
            'visible': True
        },
        {
            'id': '144:5700',
            'name': 'Frame 2121316739',
            'type': 'FRAME',
            'absoluteBoundingBox': {'x': -455, 'y': 2879, 'width': 358, 'height': 52},
            'visible': True
        },
        {
            'id': '144:3335',
            'name': 'Frame 2121316738',
            'type': 'FRAME',
            'absoluteBoundingBox': {'x': -455, 'y': 2955, 'width': 358, 'height': 996},
            'visible': True
        },
        {
            'id': '210:31',
            'name': 'Welcome username',
            'type': 'TEXT',
            'absoluteBoundingBox': {'x': -374, 'y': 2887, 'width': 164, 'height': 24},
            'visible': True,
            'characters': 'Welcome username',
            'style': {}
        }
    ]
}

# Test layout detection
from generators.swiftui_generator import generate_swiftui_code

print("=" * 60)
print("MOBILE SCROLL DETECTION TEST")
print("=" * 60)

# Node bilgileri
bbox = mock_node['absoluteBoundingBox']
width = bbox['width']
height = bbox['height']

print(f"\nNode: {mock_node['name']}")
print(f"Size: {width}×{height}")
print(f"Is Mobile Width (375-430)? {375 <= width <= 430}")
print(f"Is Tall Content (>900)? {height > 900}")
print(f"Aspect Ratio: {height/width:.2f} (>2.5? {height/width > 2.5})")

# Generate code
print("\nGenerating SwiftUI code...")
code = generate_swiftui_code(mock_node, "TestScreen")

# Check result
print("\n" + "=" * 60)
print("RESULT:")
print("=" * 60)

if "ScrollView(showsIndicators: false)" in code and "VStack" in code:
    print("✅ SUCCESS: ScrollView + VStack kullanılıyor!")
    print("✅ Mobil scroll detection çalıştı!")
elif "ScrollView" in code:
    print("⚠️  PARTIAL: ScrollView var ama horizontal olabilir")
elif "ZStack" in code and ".offset" in code:
    print("❌ FAIL: Hala ZStack + offset kullanılıyor")
    print("❌ Mobil scroll detection çalışmadı!")
else:
    print("❓ UNKNOWN: Beklenmeyen yapı")

# Preview first 50 lines
print("\nKod önizleme (ilk 50 satır):")
print("-" * 60)
lines = code.split('\n')
for i, line in enumerate(lines[:50], 1):
    print(f"{i:3}: {line}")

if len(lines) > 50:
    print(f"\n... (+{len(lines)-50} more lines)")
