from flask import Flask, request, jsonify
from dotenv import load_dotenv
import openai
import os
import boto3
import re
import requests
from triposr_integration import generate_3d_model

app = Flask(__name__)

load_dotenv()


openai.api_key = os.getenv["GPT4_API_KEY"]


def extract_plant_name(plant_info):
    # Assuming the plant name is mentioned in the first sentence
    first_sentence = plant_info.split(".")[0]
    # Extract the plant name using regular expressions
    match = re.search(r"([\w\s]+)", first_sentence)
    if match:
        return match.group(1).strip()
    else:
        return None


def save_image(image_url, plant_name):
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(f"{plant_name}.jpg", "wb") as file:
            file.write(response.content)


def generate_glb(image_path):
    output_dir = "path/to/output/directory"
    glb_file = generate_3d_model(image_path, output_dir)
    return glb_file


def process_with_gpt4(text):
    response = openai.Completion.create(
        engine="gpt-4",
        prompt=text,
        max_tokens=100,
        n=1,
        stop=None,
        temperature=0.7,
    )
    plant_info = response.choices[0].text.strip()
    # Extract plant name from the response
    plant_name = extract_plant_name(plant_info)
    return plant_name


def generate_plant_image(plant_name):
    response = openai.Image.create(
        prompt=f"A photo of a {plant_name}",
        n=1,
        size="1024x1024",
    )
    image_url = response["data"][0]["url"]
    # Download and save the image locally
    save_image(image_url, plant_name)
    return f"{plant_name}.jpg"


s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv["AWS_ACCESS_KEY"],
    aws_secret_access_key=os.getenv["AWS_SECRET_KEY"],
)


def upload_to_s3(glb_file):
    bucket_name = "your-bucket-name"
    s3.upload_file(glb_file, bucket_name, glb_file)
    glb_url = f"https://{bucket_name}.s3.amazonaws.com/{glb_file}"
    return glb_url


@app.route("/process-text", methods=["POST"])
def process_text():
    text = request.json["text"]
    plant_name = process_with_gpt4(text)
    image_path = generate_plant_image(plant_name)
    glb_file = generate_glb(image_path)
    glb_url = upload_to_s3(glb_file)
    return jsonify({"glb_url": glb_url})
