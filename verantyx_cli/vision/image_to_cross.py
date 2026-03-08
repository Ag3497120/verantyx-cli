"""
Image to Cross Structure Conversion

Converts images to Cross structure using point-based representation and simulation.
This allows CLI to "see" images by representing them as Cross 6-axis structures.

Architecture:
1. Load image → Extract pixel data
2. Convert pixels to point cloud (x, y, brightness)
3. Map points to Cross 6-axis structure (UP/DOWN, FRONT/BACK, RIGHT/LEFT)
4. Generate Cross structure with spatial relationships
5. Simulate visual understanding through Cross patterns

This is a world-model approach where images become navigable Cross structures.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import json
from dataclasses import dataclass
from datetime import datetime

try:
    from PIL import Image
    import numpy as np
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


@dataclass
class CrossPoint:
    """A point in Cross structure space"""
    x: float  # RIGHT/LEFT axis
    y: float  # UP/DOWN axis
    z: float  # FRONT/BACK axis (depth/brightness)
    intensity: float  # Brightness/color intensity
    color: Optional[Tuple[int, int, int]] = None  # RGB color


@dataclass
class CrossRegion:
    """A region in Cross structure"""
    center: CrossPoint
    points: List[CrossPoint]
    pattern: str  # Pattern type: "edge", "region", "object", etc.
    relations: List[str]  # Relations to other regions


class ImageToCross:
    """
    Converts images to Cross structure representation

    Uses point-based simulation to "recognize" images without direct visual capabilities.
    """

    # Preset quality levels
    QUALITY_PRESETS = {
        'low': {'max_points': 500, 'downsample_factor': 8},
        'medium': {'max_points': 1000, 'downsample_factor': 4},
        'high': {'max_points': 5000, 'downsample_factor': 2},
        'ultra': {'max_points': 10000, 'downsample_factor': 1},
        'maximum': {'max_points': 50000, 'downsample_factor': 1},
    }

    def __init__(
        self,
        max_points: int = 1000,
        downsample_factor: int = 4,
        quality: Optional[str] = None
    ):
        """
        Initialize image converter

        Args:
            max_points: Maximum number of points to extract (for performance)
            downsample_factor: Factor to downsample image (reduces size)
            quality: Quality preset ('low', 'medium', 'high', 'ultra', 'maximum')
                    If provided, overrides max_points and downsample_factor
        """
        if not VISION_AVAILABLE:
            raise ImportError(
                "Vision support not available. Install with: pip install pillow numpy"
            )

        # Apply quality preset if specified
        if quality and quality in self.QUALITY_PRESETS:
            preset = self.QUALITY_PRESETS[quality]
            self.max_points = preset['max_points']
            self.downsample_factor = preset['downsample_factor']
        else:
            self.max_points = max_points
            self.downsample_factor = downsample_factor

    def convert_image_file(self, image_path: Path) -> Dict[str, Any]:
        """
        Convert image file to Cross structure

        Args:
            image_path: Path to image file

        Returns:
            Cross structure dict with spatial representation
        """
        # Load image
        img = Image.open(image_path)

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Downsample for performance
        if self.downsample_factor > 1:
            new_size = (
                img.width // self.downsample_factor,
                img.height // self.downsample_factor
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to numpy array
        img_array = np.array(img)

        # Extract points
        points = self._extract_points(img_array)

        # Detect regions and patterns
        regions = self._detect_regions(points)

        # Generate Cross structure
        cross_structure = self._generate_cross_structure(
            image_path=image_path,
            image_size=(img.width, img.height),
            points=points,
            regions=regions
        )

        return cross_structure

    def _extract_points(self, img_array: np.ndarray) -> List[CrossPoint]:
        """
        Extract significant points from image

        Uses edge detection and intensity sampling to find key points.
        """
        height, width, channels = img_array.shape

        # Convert to grayscale for edge detection
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # Detect edges using simple gradient
        edges_y = np.abs(np.diff(gray, axis=0, prepend=0))
        edges_x = np.abs(np.diff(gray, axis=1, prepend=0))
        edge_magnitude = np.sqrt(edges_x**2 + edges_y**2)

        # Find significant points (high edge magnitude or regular sampling)
        points = []

        # Sample high-edge points
        edge_threshold = np.percentile(edge_magnitude, 80)
        edge_points = np.argwhere(edge_magnitude > edge_threshold)

        for y, x in edge_points:
            if len(points) >= self.max_points * 0.7:  # 70% from edges
                break

            # Normalize coordinates to [-1, 1]
            norm_x = (x / width) * 2 - 1
            norm_y = (y / height) * 2 - 1

            # Use intensity as depth (z-axis)
            intensity = gray[y, x] / 255.0
            norm_z = intensity * 2 - 1

            # Get color
            color = tuple(img_array[y, x])

            points.append(CrossPoint(
                x=norm_x,
                y=norm_y,
                z=norm_z,
                intensity=intensity,
                color=color
            ))

        # Sample regular grid for remaining points
        remaining = self.max_points - len(points)
        if remaining > 0:
            step = max(1, int(np.sqrt(height * width / remaining)))

            for y in range(0, height, step):
                for x in range(0, width, step):
                    if len(points) >= self.max_points:
                        break

                    norm_x = (x / width) * 2 - 1
                    norm_y = (y / height) * 2 - 1
                    intensity = gray[y, x] / 255.0
                    norm_z = intensity * 2 - 1
                    color = tuple(img_array[y, x])

                    points.append(CrossPoint(
                        x=norm_x,
                        y=norm_y,
                        z=norm_z,
                        intensity=intensity,
                        color=color
                    ))

        return points[:self.max_points]

    def _detect_regions(self, points: List[CrossPoint]) -> List[CrossRegion]:
        """
        Detect regions and patterns in point cloud

        Uses simple clustering and spatial analysis.
        """
        if not points:
            return []

        regions = []

        # Simple quadrant-based clustering
        quadrants = {
            'top_left': [],
            'top_right': [],
            'bottom_left': [],
            'bottom_right': [],
            'center': []
        }

        for point in points:
            # Determine quadrant
            if abs(point.x) < 0.3 and abs(point.y) < 0.3:
                quadrants['center'].append(point)
            elif point.x < 0 and point.y > 0:
                quadrants['top_left'].append(point)
            elif point.x >= 0 and point.y > 0:
                quadrants['top_right'].append(point)
            elif point.x < 0 and point.y <= 0:
                quadrants['bottom_left'].append(point)
            else:
                quadrants['bottom_right'].append(point)

        # Create regions for each quadrant
        for quadrant_name, quadrant_points in quadrants.items():
            if not quadrant_points:
                continue

            # Calculate center
            center_x = np.mean([p.x for p in quadrant_points])
            center_y = np.mean([p.y for p in quadrant_points])
            center_z = np.mean([p.z for p in quadrant_points])
            center_intensity = np.mean([p.intensity for p in quadrant_points])

            center = CrossPoint(
                x=center_x,
                y=center_y,
                z=center_z,
                intensity=center_intensity
            )

            # Detect pattern type
            intensity_variance = np.var([p.intensity for p in quadrant_points])
            if intensity_variance > 0.1:
                pattern = "edge"
            elif center_intensity > 0.7:
                pattern = "bright_region"
            elif center_intensity < 0.3:
                pattern = "dark_region"
            else:
                pattern = "mid_region"

            regions.append(CrossRegion(
                center=center,
                points=quadrant_points,
                pattern=pattern,
                relations=[quadrant_name]
            ))

        return regions

    def _generate_cross_structure(
        self,
        image_path: Path,
        image_size: Tuple[int, int],
        points: List[CrossPoint],
        regions: List[CrossRegion]
    ) -> Dict[str, Any]:
        """
        Generate Cross structure representation

        Maps image to 6-axis Cross structure:
        - RIGHT/LEFT: X-axis (horizontal position)
        - UP/DOWN: Y-axis (vertical position)
        - FRONT/BACK: Z-axis (depth/brightness)
        """
        width, height = image_size

        # Build Cross structure
        cross_structure = {
            "type": "vision_cross",
            "source": str(image_path),
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "original_size": {"width": width, "height": height},
                "num_points": len(points),
                "num_regions": len(regions)
            },

            # 6-axis representation
            "axes": {
                "RIGHT_LEFT": self._analyze_axis(points, axis='x'),
                "UP_DOWN": self._analyze_axis(points, axis='y'),
                "FRONT_BACK": self._analyze_axis(points, axis='z')
            },

            # Regions and patterns
            "regions": [
                {
                    "center": {
                        "x": r.center.x,
                        "y": r.center.y,
                        "z": r.center.z,
                        "intensity": r.center.intensity
                    },
                    "pattern": r.pattern,
                    "relations": r.relations,
                    "num_points": len(r.points)
                }
                for r in regions
            ],

            # Spatial relationships
            "spatial_relations": self._detect_spatial_relations(regions),

            # Summary description (for LLM understanding)
            "description": self._generate_description(image_path, regions)
        }

        return cross_structure

    def _analyze_axis(self, points: List[CrossPoint], axis: str) -> Dict[str, Any]:
        """Analyze distribution along one axis"""
        if axis == 'x':
            values = [p.x for p in points]
            axis_name = "RIGHT_LEFT"
        elif axis == 'y':
            values = [p.y for p in points]
            axis_name = "UP_DOWN"
        else:  # z
            values = [p.z for p in points]
            axis_name = "FRONT_BACK"

        return {
            "axis": axis_name,
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "distribution": "uniform" if np.std(values) > 0.5 else "concentrated"
        }

    def _detect_spatial_relations(self, regions: List[CrossRegion]) -> List[Dict[str, str]]:
        """Detect spatial relationships between regions"""
        relations = []

        for i, region1 in enumerate(regions):
            for region2 in regions[i+1:]:
                # Calculate relative position
                dx = region2.center.x - region1.center.x
                dy = region2.center.y - region1.center.y
                dz = region2.center.z - region1.center.z

                # Determine primary relationship
                if abs(dx) > abs(dy) and abs(dx) > abs(dz):
                    relation = "right_of" if dx > 0 else "left_of"
                elif abs(dy) > abs(dz):
                    relation = "above" if dy > 0 else "below"
                else:
                    relation = "in_front_of" if dz > 0 else "behind"

                relations.append({
                    "from": region1.pattern,
                    "to": region2.pattern,
                    "relation": relation,
                    "distance": float(np.sqrt(dx**2 + dy**2 + dz**2))
                })

        return relations

    def _generate_description(
        self,
        image_path: Path,
        regions: List[CrossRegion]
    ) -> str:
        """Generate natural language description for LLM"""
        descriptions = [
            f"Image: {image_path.name}",
            f"Detected {len(regions)} regions:"
        ]

        for region in regions:
            position = region.relations[0] if region.relations else "center"
            descriptions.append(
                f"  - {region.pattern} in {position} "
                f"(intensity: {region.center.intensity:.2f}, "
                f"{len(region.points)} points)"
            )

        return "\n".join(descriptions)


def convert_image_to_cross(
    image_path: Path,
    output_path: Optional[Path] = None,
    quality: str = 'medium',
    max_points: Optional[int] = None
) -> Dict[str, Any]:
    """
    Convenience function to convert image to Cross structure

    Args:
        image_path: Path to image file
        output_path: Optional path to save Cross structure JSON
        quality: Quality preset ('low', 'medium', 'high', 'ultra', 'maximum')
        max_points: Override max points (ignores quality preset if provided)

    Returns:
        Cross structure dict
    """
    if max_points is not None:
        # Custom point count
        converter = ImageToCross(max_points=max_points, downsample_factor=1)
    else:
        # Use quality preset
        converter = ImageToCross(quality=quality)

    cross_structure = converter.convert_image_file(image_path)

    # Save if output path provided
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(cross_structure, f, indent=2)

    return cross_structure
