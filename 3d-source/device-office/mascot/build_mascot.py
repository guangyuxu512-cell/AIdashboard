"""Build the static Device Center mascot V1 with Blender 5.2.

This is an art-source asset generator. It intentionally creates no rig and no
animation clips, and it never writes to frontend/public.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


SOURCE_DIR = Path(__file__).resolve().parent
BLEND_PATH = SOURCE_DIR / "mascot-v1.blend"
GLB_PATH = SOURCE_DIR / "mascot-v1-static.glb"
RENDER_DIR = SOURCE_DIR / "renders"

ASSET_COLLECTION = "MascotAsset"
RENDER_COLLECTION = "RenderHelpers"
SCALE_COLLECTION = "ScaleGuides"


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for item in list(data_collection):
            data_collection.remove(item)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)
    root_collection = bpy.data.collections.get("Collection")
    if root_collection:
        root_collection.name = ASSET_COLLECTION


def collection(name: str) -> bpy.types.Collection:
    found = bpy.data.collections.get(name)
    if found:
        return found
    created = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(created)
    return created


def move_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def set_principled_input(
    material: bpy.types.Material,
    name: str,
    value: float | tuple[float, float, float, float],
) -> None:
    node = material.node_tree.nodes.get("Principled BSDF")
    if node and name in node.inputs:
        node.inputs[name].default_value = value


def make_material(
    name: str,
    base_color: tuple[float, float, float, float],
    *,
    metallic: float,
    roughness: float,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.12,
    emission_color: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = base_color
    set_principled_input(material, "Base Color", base_color)
    set_principled_input(material, "Metallic", metallic)
    set_principled_input(material, "Roughness", roughness)
    set_principled_input(material, "Coat Weight", coat_weight)
    set_principled_input(material, "Coat Roughness", coat_roughness)
    if emission_color:
        set_principled_input(material, "Emission Color", emission_color)
        set_principled_input(material, "Emission Strength", emission_strength)
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(material)


def smooth_mesh(obj: bpy.types.Object) -> None:
    if obj.type != "MESH":
        return
    for polygon in obj.data.polygons:
        polygon.use_smooth = True


def apply_transform(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


def superellipsoid(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material: bpy.types.Material,
    *,
    exponent: float = 0.78,
    segments: int = 40,
    rings: int = 20,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    radii = tuple(value / 2.0 for value in dimensions)
    for vertex in obj.data.vertices:
        original = vertex.co.copy()
        vertex.co.x = radii[0] * math.copysign(abs(original.x) ** exponent, original.x)
        vertex.co.y = radii[1] * math.copysign(abs(original.y) ** exponent, original.y)
        vertex.co.z = radii[2] * math.copysign(abs(original.z) ** exponent, original.z)
    assign_material(obj, material)
    smooth_mesh(obj)
    apply_transform(obj)
    return obj


def rounded_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    bevel: float,
    material: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    segments: int = 6,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    apply_transform(obj)
    modifier = obj.modifiers.new("DesignBevel", "BEVEL")
    modifier.width = bevel
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    assign_material(obj, material)
    smooth_mesh(obj)
    return obj


def cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    material: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    vertices: int = 32,
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    if bevel:
        modifier = obj.modifiers.new("EdgeSoftening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 4
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    assign_material(obj, material)
    smooth_mesh(obj)
    apply_transform(obj)
    return obj


def torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    material: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=40,
        minor_segments=10,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    assign_material(obj, material)
    smooth_mesh(obj)
    apply_transform(obj)
    return obj


def mouth_mesh(material: bpy.types.Material) -> bpy.types.Object:
    curve = bpy.data.curves.new("MouthCurve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = 0.009
    curve.bevel_resolution = 4
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(2)
    points = [(-0.075, -0.467, 0.920), (0.0, -0.477, 0.900), (0.075, -0.467, 0.920)]
    for point, coordinate in zip(spline.bezier_points, points, strict=True):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new("Mouth", curve)
    bpy.data.collections[ASSET_COLLECTION].objects.link(obj)
    curve.materials.append(material)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj.select_set(False)
    return obj


def text_mesh(
    name: str,
    body: str,
    location: tuple[float, float, float],
    size: float,
    material: bpy.types.Material,
    *,
    rotation: tuple[float, float, float],
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}Curve", "FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.003
    curve.bevel_depth = 0.0015
    curve.bevel_resolution = 2
    obj = bpy.data.objects.new(name, curve)
    obj.location = location
    obj.rotation_euler = rotation
    bpy.data.collections[ASSET_COLLECTION].objects.link(obj)
    curve.materials.append(material)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    apply_transform(obj)
    obj.select_set(False)
    return obj


def join_objects(name: str, objects: list[bpy.types.Object]) -> bpy.types.Object:
    if len(objects) == 1:
        objects[0].name = name
        return objects[0]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.object
    joined.name = name
    joined.select_set(False)
    return joined


def parent_to_root(root: bpy.types.Object, objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        obj.parent = root
        obj.matrix_parent_inverse = root.matrix_world.inverted()


def build_asset() -> tuple[bpy.types.Object, list[bpy.types.Object], dict[str, bpy.types.Material]]:
    asset_collection = bpy.data.collections[ASSET_COLLECTION]
    shell = make_material(
        "Mascot_Shell",
        (0.88, 0.87, 0.84, 1.0),
        metallic=0.0,
        roughness=0.30,
        coat_weight=0.28,
        coat_roughness=0.16,
    )
    visor = make_material(
        "Mascot_Visor",
        (0.006, 0.018, 0.038, 1.0),
        metallic=0.32,
        roughness=0.10,
        coat_weight=0.65,
        coat_roughness=0.06,
    )
    eyes_material = make_material(
        "Mascot_Eyes",
        (0.0, 0.34, 0.82, 1.0),
        metallic=0.0,
        roughness=0.22,
        emission_color=(0.0, 0.56, 1.0, 1.0),
        emission_strength=1.35,
    )
    accent = make_material(
        "Mascot_Accent",
        (0.015, 0.18, 0.78, 1.0),
        metallic=0.18,
        roughness=0.24,
        coat_weight=0.32,
        coat_roughness=0.10,
    )
    materials = {"Shell": shell, "Visor": visor, "Eyes": eyes_material, "Accent": accent}

    root = bpy.data.objects.new("AvatarRoot", None)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 0.18
    asset_collection.objects.link(root)

    head = superellipsoid(
        "HeadShell",
        (0.0, 0.0, 0.995),
        (0.92, 0.78, 0.75),
        shell,
        exponent=0.86,
        segments=48,
        rings=24,
    )
    face = superellipsoid(
        "FaceVisor",
        (0.0, -0.371, 0.995),
        (0.74, 0.145, 0.405),
        visor,
        exponent=0.66,
        segments=48,
        rings=24,
    )

    eye_parts = [
        superellipsoid(
            "EyeLeft",
            (-0.155, -0.451, 1.025),
            (0.088, 0.028, 0.145),
            eyes_material,
            exponent=0.72,
            segments=28,
            rings=14,
        ),
        superellipsoid(
            "EyeRight",
            (0.155, -0.451, 1.025),
            (0.088, 0.028, 0.145),
            eyes_material,
            exponent=0.72,
            segments=28,
            rings=14,
        ),
        mouth_mesh(eyes_material),
    ]
    eyes = join_objects("Eyes", eye_parts)

    body = superellipsoid(
        "BodyShell",
        (0.0, 0.012, 0.470),
        (0.53, 0.39, 0.48),
        shell,
        exponent=0.74,
        segments=40,
        rings=20,
    )

    arm_parts = [
        superellipsoid(
            "ArmLeft",
            (-0.315, -0.005, 0.490),
            (0.145, 0.155, 0.300),
            shell,
            exponent=0.92,
            segments=28,
            rings=14,
            rotation=(0.0, -0.20, -0.12),
        ),
        superellipsoid(
            "ArmRight",
            (0.315, -0.005, 0.490),
            (0.145, 0.155, 0.300),
            shell,
            exponent=0.92,
            segments=28,
            rings=14,
            rotation=(0.0, 0.20, 0.12),
        ),
    ]
    arms = join_objects("Arms", arm_parts)

    hand_parts = [
        superellipsoid(
            "HandLeft",
            (-0.337, -0.030, 0.335),
            (0.145, 0.145, 0.150),
            shell,
            exponent=0.78,
            segments=24,
            rings=12,
        ),
        superellipsoid(
            "HandRight",
            (0.337, -0.030, 0.335),
            (0.145, 0.145, 0.150),
            shell,
            exponent=0.78,
            segments=24,
            rings=12,
        ),
    ]
    hands = join_objects("Hands", hand_parts)

    leg_parts = [
        superellipsoid(
            "LegLeft",
            (-0.125, 0.015, 0.205),
            (0.145, 0.155, 0.225),
            shell,
            exponent=0.88,
            segments=24,
            rings=12,
        ),
        superellipsoid(
            "LegRight",
            (0.125, 0.015, 0.205),
            (0.145, 0.155, 0.225),
            shell,
            exponent=0.88,
            segments=24,
            rings=12,
        ),
    ]
    legs = join_objects("Legs", leg_parts)

    foot_parts = [
        rounded_box("FootLeft", (-0.130, -0.030, 0.065), (0.205, 0.265, 0.13), 0.058, shell),
        rounded_box("FootRight", (0.130, -0.030, 0.065), (0.205, 0.265, 0.13), 0.058, shell),
        rounded_box("SoleLeft", (-0.130, -0.076, 0.029), (0.190, 0.205, 0.058), 0.025, visor),
        rounded_box("SoleRight", (0.130, -0.076, 0.029), (0.190, 0.205, 0.058), 0.025, visor),
    ]
    feet = join_objects("Feet", foot_parts)

    antenna_parts = [
        cylinder(
            "AntennaStem",
            (0.030, 0.012, 1.415),
            0.018,
            0.145,
            visor,
            rotation=(-0.16, 0.0, 0.0),
            vertices=24,
            bevel=0.008,
        ),
    ]
    antenna = join_objects("Antenna", antenna_parts)

    accent_parts = [
        torus(
            "EarFrameLeft",
            (-0.466, 0.0, 0.995),
            0.120,
            0.020,
            visor,
            rotation=(0.0, math.pi / 2.0, 0.0),
        ),
        torus(
            "EarFrameRight",
            (0.466, 0.0, 0.995),
            0.120,
            0.020,
            visor,
            rotation=(0.0, math.pi / 2.0, 0.0),
        ),
        cylinder(
            "EarPlateLeft",
            (-0.471, 0.0, 0.995),
            0.094,
            0.038,
            accent,
            rotation=(0.0, math.pi / 2.0, 0.0),
            vertices=32,
            bevel=0.012,
        ),
        cylinder(
            "EarPlateRight",
            (0.471, 0.0, 0.995),
            0.094,
            0.038,
            accent,
            rotation=(0.0, math.pi / 2.0, 0.0),
            vertices=32,
            bevel=0.012,
        ),
        superellipsoid("ShoulderAccentLeft", (-0.250, -0.010, 0.715), (0.17, 0.20, 0.080), accent, exponent=0.76, segments=24, rings=12, rotation=(0.0, -0.22, -0.08)),
        superellipsoid("ShoulderAccentRight", (0.250, -0.010, 0.715), (0.17, 0.20, 0.080), accent, exponent=0.76, segments=24, rings=12, rotation=(0.0, 0.22, 0.08)),
        superellipsoid("NeckAccent", (0.0, -0.010, 0.725), (0.20, 0.18, 0.075), accent, exponent=0.78, segments=24, rings=12),
        rounded_box("BackModule", (0.0, 0.215, 0.495), (0.30, 0.105, 0.33), 0.052, accent),
        superellipsoid("AntennaTip", (0.030, 0.025, 1.495), (0.105, 0.105, 0.105), accent, exponent=0.82, segments=24, rings=12),
        text_mesh("ChestMark", "DC", (0.0, -0.205, 0.495), 0.115, accent, rotation=(math.pi / 2.0, 0.0, 0.0)),
        text_mesh("EarMarkLeft", "DC", (-0.493, 0.0, 0.995), 0.055, shell, rotation=(math.pi / 2.0, 0.0, -math.pi / 2.0)),
        text_mesh("EarMarkRight", "DC", (0.493, 0.0, 0.995), 0.055, shell, rotation=(math.pi / 2.0, 0.0, math.pi / 2.0)),
        text_mesh("BackMark", "D", (0.0, 0.274, 0.495), 0.105, shell, rotation=(math.pi / 2.0, 0.0, math.pi)),
    ]
    accent_object = join_objects("Accent", accent_parts)

    belt = torus("Belt", (0.0, 0.0, 0.285), 0.215, 0.014, visor)
    belt.scale.y = 0.70
    apply_transform(belt)

    asset_objects = [head, face, eyes, body, arms, hands, legs, feet, antenna, accent_object, belt]
    parent_to_root(root, asset_objects)

    for anchor_name, location in (
        ("AccessoryHeadset", (0.0, 0.0, 0.995)),
        ("AccessoryScarf", (0.0, 0.0, 0.725)),
        ("AccessoryBadge", (0.0, -0.205, 0.495)),
    ):
        anchor = bpy.data.objects.new(anchor_name, None)
        anchor.location = location
        anchor.empty_display_type = "PLAIN_AXES"
        anchor.empty_display_size = 0.08
        asset_collection.objects.link(anchor)
        anchor.parent = root
        asset_objects.append(anchor)

    return root, asset_objects, materials


def make_render_material(name: str, color: tuple[float, float, float, float], roughness: float) -> bpy.types.Material:
    return make_material(name, color, metallic=0.0, roughness=roughness)


def create_render_setup() -> tuple[bpy.types.Object, bpy.types.Collection]:
    render_collection = collection(RENDER_COLLECTION)
    scale_collection = collection(SCALE_COLLECTION)
    ground_material = make_render_material("Render_Ground", (0.115, 0.135, 0.165, 1.0), 0.72)
    grid_material = make_render_material("Render_Grid", (0.22, 0.29, 0.36, 1.0), 0.55)
    marker_material = make_render_material("Render_Marker", (0.08, 0.42, 0.68, 1.0), 0.35)

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = "RenderGround"
    assign_material(ground, ground_material)
    move_to_collection(ground, render_collection)

    camera_data = bpy.data.cameras.new("RenderCamera")
    camera = bpy.data.objects.new("RenderCamera", camera_data)
    render_collection.objects.link(camera)
    camera_data.lens = 70
    camera_data.sensor_width = 36
    bpy.context.scene.camera = camera

    for name, light_type, energy, color, location, size in (
        ("KeyLight", "AREA", 900.0, (0.78, 0.90, 1.0), (-3.2, -4.0, 5.0), 4.0),
        ("FillLight", "AREA", 650.0, (0.45, 0.72, 1.0), (3.5, -2.0, 2.6), 3.0),
        ("RimLight", "AREA", 1050.0, (0.25, 0.55, 1.0), (0.5, 3.5, 4.2), 2.5),
    ):
        light_data = bpy.data.lights.new(name, light_type)
        light_data.energy = energy
        light_data.color = color
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        light.location = location
        render_collection.objects.link(light)
        point_at(light, (0.0, 0.0, 0.75))

    for index in range(-4, 5):
        offset = index * 0.5
        for axis in ("x", "y"):
            dimensions = (4.0, 0.008, 0.004) if axis == "x" else (0.008, 4.0, 0.004)
            location = (0.0, offset, 0.003) if axis == "x" else (offset, 0.0, 0.003)
            guide = rounded_box(
                f"Grid_{axis}_{index}",
                location,
                dimensions,
                0.002,
                grid_material,
                segments=2,
            )
            move_to_collection(guide, scale_collection)
    marker = cylinder("ScaleMarker", (-0.78, 0.25, 0.75), 0.018, 1.5, marker_material, vertices=16)
    move_to_collection(marker, scale_collection)
    for height in (0.5, 1.0, 1.5):
        tick = rounded_box(
            f"ScaleTick_{height}",
            (-0.70, 0.25, height),
            (0.16, 0.018, 0.018),
            0.006,
            marker_material,
            segments=2,
        )
        move_to_collection(tick, scale_collection)
    scale_collection.hide_render = True
    return camera, scale_collection


def point_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_render() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(RENDER_DIR / "preview.png")
    scene.render.use_file_extension = True
    scene.world.color = (0.025, 0.035, 0.055)
    scene.view_settings.look = "AgX - Medium High Contrast"


def render_views(camera: bpy.types.Object, scale_guides: bpy.types.Collection) -> None:
    views = (
        ("01_front.png", (0.0, -4.0, 1.32), (0.0, 0.0, 0.70), 72, False, (768, 768)),
        ("02_side.png", (4.0, 0.0, 1.32), (0.0, 0.0, 0.70), 72, False, (768, 768)),
        ("03_three-quarter.png", (3.0, -3.0, 1.45), (0.0, 0.0, 0.71), 70, False, (768, 768)),
        ("04_back.png", (0.0, 4.0, 1.32), (0.0, 0.0, 0.70), 72, False, (768, 768)),
        ("05_scale-preview.png", (4.4, -6.2, 3.2), (0.0, 0.0, 0.61), 55, True, (960, 640)),
    )
    for filename, position, target, lens, show_scale, resolution in views:
        camera.location = position
        camera.data.lens = lens
        point_at(camera, target)
        scale_guides.hide_render = not show_scale
        bpy.context.scene.render.resolution_x = resolution[0]
        bpy.context.scene.render.resolution_y = resolution[1]
        bpy.context.scene.render.filepath = str(RENDER_DIR / filename)
        bpy.ops.render.render(write_still=True)


def descendants(root: bpy.types.Object) -> list[bpy.types.Object]:
    output: list[bpy.types.Object] = []
    queue = list(root.children)
    while queue:
        item = queue.pop(0)
        output.append(item)
        queue.extend(item.children)
    return output


def export_static_glb(root: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    export_objects = [root, *descendants(root)]
    for obj in export_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    bpy.ops.object.select_all(action="DESELECT")


def triangle_count(objects: list[bpy.types.Object]) -> int:
    return sum(
        sum(max(0, len(polygon.vertices) - 2) for polygon in obj.data.polygons)
        for obj in objects
        if obj.type == "MESH"
    )


def asset_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def main() -> None:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    reset_scene()
    root, asset_objects, materials = build_asset()
    camera, scale_guides = create_render_setup()
    configure_render()
    export_static_glb(root)
    render_views(camera, scale_guides)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    bounds_min, bounds_max = asset_bounds(asset_objects)
    print(f"MASCOT_TRIANGLES={triangle_count(asset_objects)}")
    print(f"MASCOT_OBJECTS={len(asset_objects) + 1}")
    print(f"MASCOT_MATERIALS={len(materials)}")
    print(f"MASCOT_BOUNDS_MIN={tuple(round(value, 4) for value in bounds_min)}")
    print(f"MASCOT_BOUNDS_MAX={tuple(round(value, 4) for value in bounds_max)}")
    print(f"MASCOT_BLEND={BLEND_PATH}")
    print(f"MASCOT_GLB={GLB_PATH}")


if __name__ == "__main__":
    main()
