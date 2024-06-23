from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os
import boto3
import re
import requests
import json
# from triposr_integration import generate_3d_model

app = Flask(__name__)

load_dotenv()
client = OpenAI()
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
)

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


# def generate_glb(image_path):
#     output_dir = "path/to/output/directory"
#     glb_file = generate_3d_model(image_path, output_dir)
#     return glb_file


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

def upload_to_s3(glb_file):
    bucket_name = "greenspace"
    s3.upload_file(glb_file, bucket_name, glb_file)
    glb_url = f"https://{bucket_name}.s3.amazonaws.com/{glb_file}"
    return glb_url


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json()
    text = data["text"]
    plant_name = process_with_gpt4(text)
    image_path = generate_plant_image(plant_name)
    # glb_file = generate_glb(image_path)
    # glb_url = upload_to_s3(glb_file)
    return jsonify({"plant": plant_name})

if __name__ == '__main__':
    app.run()

# text = "I want to plant an orange tree."
# plant_name = process_with_gpt4(text)
# image_path = generate_plant_image(plant_name)
# # glb_file = generate_glb(image_path)
# glb_url = upload_to_s3(image_path)
# # return jsonify({"glb_url": glb_url})