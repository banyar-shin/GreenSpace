# triposr_integration.py
import os
from PIL import Image
from tsr.system import TSR
import torch


def generate_3d_model(image_path, output_dir):
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(device)

    image = Image.open(image_path)

    with torch.no_grad():
        scene_codes = model([image], device=device)

    meshes = model.extract_mesh(scene_codes, resolution=256)

    out_mesh_path = os.path.join(output_dir, "mesh.glb")
    meshes[0].export(out_mesh_path)

    return out_mesh_path
