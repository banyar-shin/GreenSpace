from openai import OpenAI
import json
import requests

client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  response_format={ "type": "json_object" },
  messages=[
    {"role": "system", "content": "Give me an answer in a json format like this: {'plant': {'name': '','instructions': {'watering frequency': '','pruning schedule': ''},'benefits': {'carbon sequestration': 'Very High | High | Medium | Low | Very Low','oxygen production': 'Very High | High | Medium | Low | Very Low','temperature regulation': 'Very High | High | Medium | Low | Very Low','air quality improvement': '','other benefits': ''}}}"},
    {"role": "user", "content": "I want to plant an apple tree."},
  ]
)

# Extract response message content
response_message_content = response.choices[0].message.content

# Assuming the response content is a valid JSON string
response_json = json.loads(response_message_content)

# Define the filename and path
filename = 'plant_recommendation.json'

# Write the JSON data to a file
with open(filename, 'w') as json_file:
  json.dump(response_json, json_file, indent=4)

print(f'Response saved to {filename}')

response2 = client.images.generate(
  model="dall-e-3",
  prompt="Generate a realistic image of a single " + response_json["plant"]["name"] + " tree, showing top to bottom with attention to detail, no shadows, with a plain background.",
  size="1024x1024",
  quality="standard",
  n=1,
)

image_url = response2.data[0].url
print(image_url)

# Send a GET request to the URL
response = requests.get(image_url, stream=True)

# Check if the request was successful
if response.status_code == 200:
    # Open a local file in binary write mode
    with open("downloaded_image.png", "wb") as file:
        # Write the content of the response to the file
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    print("Image downloaded successfully")
else:
    print(f"Failed to retrieve image. HTTP Status code: {response.status_code}")
