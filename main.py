from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os
import boto3
import re
import requests
import json
import argparse
import logging
import time
from botocore.exceptions import NoCredentialsError
import numpy as np
import rembg
import torch
import xatlas
from PIL import Image
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground, save_video
from tsr.bake_texture import bake_texture

app = Flask(__name__)

load_dotenv()
client = OpenAI()
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
)
bucket_name = "greenspace-berkeley-hackathon"

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

def save_image(image_url, plant_name):
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(f"{plant_name}.jpg", "wb") as file:
            file.write(response.content)

def process_with_gpt4(text):
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": "Give me an answer in a json format like this: {'plant': {'name': '','instructions': {'watering frequency': '','pruning schedule': ''},'benefits': {'carbon sequestration': 'Very High | High | Medium | Low | Very Low','oxygen production': 'Very High | High | Medium | Low | Very Low','temperature regulation': 'Very High | High | Medium | Low | Very Low','air quality improvement': '','other benefits': ''}}}"},
            {"role": "user", "content": text},
        ]
    )
    response_message_content = response.choices[0].message.content
    response_json = json.loads(response_message_content)
    filename = 'plant_recommendation.json'
    with open(filename, 'w') as json_file:
        json.dump(response_json, json_file, indent=4)
    print(f'Response saved to {filename}')

    return response_json["plant"]["name"]


def generate_plant_image(plant_name):
    response = client.images.generate(
        model="dall-e-3",
        prompt="Generate a realistic image of a single " + plant_name + " tree, showing top to bottom with attention to detail, no shadows, with a plain background.",
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    print(image_url)

    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
    # Open a local file in binary write mode
        with open(f"{plant_name}.png", "wb") as file:
            # Write the content of the response to the file
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print("Image downloaded successfully")
    else:
        print(f"Failed to retrieve image. HTTP Status code: {response.status_code}")
    return (f"{plant_name}.png")

def generate_3d_model_and_upload_to_s3(
    image_path,
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
    out_mesh_path = os.path.join("3d", f"{image_path}.{model_save_format}")
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
    try:
        s3.upload_file(out_mesh_path, bucket_name, f"threed/{image_path}.{model_save_format}")
        if bake_texture:
            s3.upload_file(out_texture_path, bucket_name, "texture.png")
        if render:
            s3.upload_file(os.path.join(temp_dir, "render.mp4"), bucket_name, "render.mp4")
        logging.info(f"Successfully uploaded to S3 bucket: {bucket_name}")
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

def upload_to_s3(file):
    folder = "img/"
    key = folder + os.path.basename(file)
    s3.upload_file(file, bucket_name, key)
    img_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
    return img_url


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json()
    text = data["text"]
    plant_name = process_with_gpt4(text)
    image_path = generate_plant_image(plant_name)
    img_url = upload_to_s3(image_path)
    generate_3d_model_and_upload_to_s3("./Peach Tree.png")
    return jsonify({"plant": plant_name})

if __name__ == '__main__':
    app.run()
