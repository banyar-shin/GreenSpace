import argparse
import logging
import os
import time
import boto3
from botocore.exceptions import NoCredentialsError
import numpy as np
import rembg
import torch
import xatlas
from PIL import Image

from dotenv import load_dotenv

from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground, save_video
from tsr.bake_texture import bake_texture


load_dotenv()


# ... (keep the Timer class and get_unique_output_dir function as they are)
class Timer:
    def __init__(self):
        self.items = {}
        self.time_scale = 1000.0  # ms
        self.time_unit = "ms"

    def start(self, name: str) -> None:
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        self.items[name] = time.time()
        logging.info(f"{name} ...")

    def end(self, name: str) -> float:
        if name not in self.items:
            return
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        start_time = self.items.pop(name)
        delta = time.time() - start_time
        t = delta * self.time_scale
        logging.info(f"{name} finished in {t:.2f}{self.time_unit}.")


def generate_3d_model_and_upload_to_s3(
    image_path,
    s3_bucket,
    device="cuda:0",
    pretrained_model_name_or_path="stabilityai/TripoSR",
    chunk_size=8192,
    mc_resolution=256,
    remove_bg=True,
    foreground_ratio=0.85,
    model_save_format="obj",
    bake_texture=False,
    texture_resolution=2048,
    render=False
):
    timer = Timer()
    
    # Set up logging
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    
    # Check for CUDA availability
    if not torch.cuda.is_available():
        device = "cpu"
    
    # Initialize model
    timer.start("Initializing model")
    model = TSR.from_pretrained(
        pretrained_model_name_or_path,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(chunk_size)
    model.to(device)
    timer.end("Initializing model")
    
    # Process image
    timer.start("Processing image")
    if not remove_bg:
        image = np.array(Image.open(image_path).convert("RGB"))
    else:
        rembg_session = rembg.new_session()
        image = remove_background(Image.open(image_path), rembg_session)
        image = resize_foreground(image, foreground_ratio)
        image = np.array(image).astype(np.float32) / 255.0
        image = image[:, :, :3] * image[:, :, 3:4] + (1 - image[:, :, 3:4]) * 0.5
        image = Image.fromarray((image * 255.0).astype(np.uint8))
    timer.end("Processing image")
    
    # Create a temporary directory for output
    temp_dir = "temp_output"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Run model
    timer.start("Running model")
    with torch.no_grad():
        scene_codes = model([image], device=device)
    timer.end("Running model")
    
    if render:
        timer.start("Rendering")
        render_images = model.render(scene_codes, n_views=30, return_type="pil")
        for ri, render_image in enumerate(render_images[0]):
            render_image.save(os.path.join(temp_dir, f"render_{ri:03d}.png"))
        save_video(render_images[0], os.path.join(temp_dir, f"render.mp4"), fps=30)
        timer.end("Rendering")
    
    # Extract mesh
    timer.start("Extracting mesh")
    meshes = model.extract_mesh(scene_codes, not bake_texture, resolution=mc_resolution)
    timer.end("Extracting mesh")
    
    # Save mesh and texture
    out_mesh_path = os.path.join(temp_dir, f"mesh.{model_save_format}")
    if bake_texture:
        out_texture_path = os.path.join(temp_dir, "texture.png")
        timer.start("Baking texture")
        bake_output = bake_texture(meshes[0], model, scene_codes[0], texture_resolution)
        timer.end("Baking texture")
        
        timer.start("Exporting mesh and texture")
        xatlas.export(
            out_mesh_path,
            meshes[0].vertices[bake_output["vmapping"]],
            bake_output["indices"],
            bake_output["uvs"],
            meshes[0].vertex_normals[bake_output["vmapping"]],
        )
        Image.fromarray((bake_output["colors"] * 255.0).astype(np.uint8)).transpose(
            Image.FLIP_TOP_BOTTOM
        ).save(out_texture_path)
        timer.end("Exporting mesh and texture")
    else:
        timer.start("Exporting mesh")
        meshes[0].export(out_mesh_path)
        timer.end("Exporting mesh")
    
    # Upload to S3
    timer.start("Uploading to S3")
    s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
)
    try:
        s3_client.upload_file(out_mesh_path, s3_bucket, f"mesh.{model_save_format}")
        if bake_texture:
            s3_client.upload_file(out_texture_path, s3_bucket, "texture.png")
        if render:
            s3_client.upload_file(os.path.join(temp_dir, "render.mp4"), s3_bucket, "render.mp4")
        logging.info(f"Successfully uploaded to S3 bucket: {s3_bucket}")
    except NoCredentialsError:
        logging.error("Credentials not available for S3 upload")
    except Exception as e:
        logging.error(f"Error uploading to S3: {str(e)}")
    timer.end("Uploading to S3")
    
    # Clean up temporary files
    for file in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, file))
    os.rmdir(temp_dir)

    logging.info("3D model generation and S3 upload complete")

# Example usage
generate_3d_model_and_upload_to_s3("./Peach Tree.png", "greenspace-berkeley-hackathon")