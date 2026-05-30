#!/usr/bin/env python3
"""Generate the documentation concept GLB for the ESP32 enclosure."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "models"
OUT_FILE = OUT_DIR / "real-shock-esp32-case-concept.glb"


def cube_vertices(size: tuple[float, float, float], center: tuple[float, float, float]) -> list[float]:
    sx, sy, sz = (v / 2 for v in size)
    cx, cy, cz = center
    corners = [
        (-sx, -sy, -sz),
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    out: list[float] = []
    for face in faces:
        for i in (face[0], face[1], face[2], face[0], face[2], face[3]):
            x, y, z = corners[i]
            out.extend([cx + x, cy + y, cz + z])
    return out


def make_mesh() -> tuple[bytes, list[dict[str, int | list[float]]]]:
    parts = [
        ((86, 5, 58), (0, 0, 0), [0.12, 0.15, 0.18, 1.0]),       # base tray
        ((78, 2, 50), (0, 4, 0), [0.18, 0.22, 0.28, 1.0]),       # inner floor
        ((66, 5, 30), (-1, 9, 0), [0.05, 0.36, 0.58, 1.0]),     # ESP32 board
        ((14, 4, 10), (-42, 10, 0), [0.72, 0.78, 0.84, 1.0]),   # USB port
        ((12, 5, 12), (29, 12, -14), [0.88, 0.22, 0.18, 1.0]),  # emergency switch
        ((5, 4, 36), (20, 10, 30), [0.86, 0.62, 0.18, 1.0]),    # wire duct
        ((20, 4, 8), (-4, 10, 30), [0.12, 0.55, 0.34, 1.0]),    # A/B/C pads
        ((3, 3, 42), (-25, 12, 25), [0.95, 0.76, 0.32, 1.0]),   # jumper bundle
        ((3, 3, 42), (-18, 12, 25), [0.83, 0.22, 0.18, 1.0]),   # jumper bundle
        ((3, 3, 42), (-11, 12, 25), [0.15, 0.15, 0.16, 1.0]),   # jumper bundle
    ]
    chunks: list[bytes] = []
    views: list[dict[str, int | list[float]]] = []
    offset = 0
    for size, center, color in parts:
        verts = cube_vertices(size, center)
        blob = struct.pack("<" + "f" * len(verts), *verts)
        chunks.append(blob)
        xs = verts[0::3]
        ys = verts[1::3]
        zs = verts[2::3]
        views.append(
            {
                "offset": offset,
                "length": len(blob),
                "count": len(verts) // 3,
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
                "color": color,
            }
        )
        offset += len(blob)
    return b"".join(chunks), views


def padded(data: bytes, pad: bytes) -> bytes:
    return data + pad * ((4 - len(data) % 4) % 4)


def main() -> None:
    binary, views = make_mesh()
    accessors = []
    buffer_views = []
    meshes = []
    for i, view in enumerate(views):
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": view["offset"],
                "byteLength": view["length"],
                "target": 34962,
            }
        )
        accessors.append(
            {
                "bufferView": i,
                "componentType": 5126,
                "count": view["count"],
                "type": "VEC3",
                "min": view["min"],
                "max": view["max"],
            }
        )
        meshes.append(
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": i},
                        "mode": 4,
                        "material": i,
                    }
                ]
            }
        )

    gltf = {
        "asset": {"version": "2.0", "generator": "real-shock-mod docs"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(meshes)))}],
        "nodes": [{"mesh": i} for i in range(len(meshes))],
        "meshes": meshes,
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": view["color"],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.82,
                },
                "doubleSided": True,
            }
            for view in views
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
    }

    json_chunk = padded(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bin_chunk = padded(binary, b"\0")
    glb = (
        b"glTF"
        + struct.pack("<II", 2, 12 + 8 + len(json_chunk) + 8 + len(bin_chunk))
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\0")
        + bin_chunk
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes(glb)
    print(f"wrote {OUT_FILE.relative_to(ROOT)} ({math.ceil(len(glb) / 1024)} KB)")


if __name__ == "__main__":
    main()
