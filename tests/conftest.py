"""Shared test fixtures for generator tests."""
import pytest


@pytest.fixture
def node_with_dashed_stroke():
    """Figma node with dashed border stroke."""
    return {
        'type': 'RECTANGLE',
        'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
        'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 1, 'g': 1, 'b': 1, 'a': 1}, 'opacity': 1}],
        'strokes': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0, 'g': 0, 'b': 0, 'a': 1}, 'opacity': 1}],
        'strokeWeight': 2,
        'strokeAlign': 'INSIDE',
        'strokeDashes': [5, 3],
        'effects': [],
        'children': [],
    }


@pytest.fixture
def node_with_individual_borders():
    """Figma node with different border widths per side."""
    return {
        'type': 'RECTANGLE',
        'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
        'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 1, 'g': 1, 'b': 1, 'a': 1}, 'opacity': 1}],
        'strokes': [{'type': 'SOLID', 'visible': True, 'color': {'r': 0, 'g': 0, 'b': 0, 'a': 1}, 'opacity': 1}],
        'strokeWeight': 1,
        'strokeTopWeight': 2,
        'strokeRightWeight': 0,
        'strokeBottomWeight': 4,
        'strokeLeftWeight': 0,
        'strokeAlign': 'INSIDE',
        'effects': [],
        'children': [],
    }


@pytest.fixture
def node_with_background_blur():
    """Figma node with BACKGROUND_BLUR effect."""
    return {
        'type': 'RECTANGLE',
        'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
        'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 1, 'g': 1, 'b': 1, 'a': 0.5}, 'opacity': 0.5}],
        'strokes': [],
        'effects': [{'type': 'BACKGROUND_BLUR', 'visible': True, 'radius': 10}],
        'children': [],
    }


@pytest.fixture
def node_with_inner_shadow():
    """Figma node with INNER_SHADOW effect."""
    return {
        'type': 'RECTANGLE',
        'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 200, 'height': 100},
        'fills': [{'type': 'SOLID', 'visible': True, 'color': {'r': 1, 'g': 1, 'b': 1, 'a': 1}, 'opacity': 1}],
        'strokes': [],
        'effects': [{
            'type': 'INNER_SHADOW', 'visible': True, 'radius': 4, 'spread': 0,
            'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0.25},
            'offset': {'x': 0, 'y': 2}
        }],
        'children': [],
    }


@pytest.fixture
def node_with_radial_gradient():
    """Figma node with RADIAL gradient fill (300x150 dimensions)."""
    return {
        'type': 'RECTANGLE',
        'absoluteBoundingBox': {'x': 0, 'y': 0, 'width': 300, 'height': 150},
        'fills': [{
            'type': 'GRADIENT_RADIAL', 'visible': True, 'opacity': 1,
            'gradientStops': [
                {'color': {'r': 1, 'g': 0, 'b': 0, 'a': 1}, 'position': 0},
                {'color': {'r': 0, 'g': 0, 'b': 1, 'a': 1}, 'position': 1},
            ],
            'gradientHandlePositions': [
                {'x': 0.5, 'y': 0.5},
                {'x': 1.0, 'y': 0.5},
                {'x': 0.5, 'y': 1.0},
            ]
        }],
        'strokes': [],
        'effects': [],
        'children': [],
    }
