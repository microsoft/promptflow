import argparse
import base64
import os
import io
from PIL import Image


SUPPORT_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "bmp"]


def get_image_size(image_path):
    with Image.open(image_path) as img:
        width, height = img.size
    return width, height


def get_image_storage_size(image_path):
    file_size_bytes = os.path.getsize(image_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return file_size_mb


def image_to_data_url(image_path):
    with open(image_path, "rb") as image_file:
        # Create a BytesIO object from the image file
        image_data = io.BytesIO(image_file.read())

    # Open the image and resize it
    img = Image.open(image_data)
    if img.size != (16, 16):
        img = img.resize((16, 16), Image.Resampling.LANCZOS)

    # Save the resized image to a data URL
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    data_url = 'data:image/png;base64,' + img_str.decode('utf-8')

    return data_url


def create_html_file(data_uri, output_path):
    html_content = '<html>\n<body>\n<img src="{}" alt="My Image">\n</body>\n</html>'.format(data_uri)

    with open(output_path, 'w') as file:
        file.write(html_content)


def check_image_type(image_path):
    file_extension = image_path.lower().split('.')[-1]
    if file_extension not in SUPPORT_IMAGE_TYPES:
        raise ValueError("Only png, jpg, gif, or bmp image types are supported.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image-path",
        type=str,
        required=True,
        help="Your image input path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Your image output path",
    )
    args = parser.parse_args()
    check_image_type(args.image_path)
    data_url = image_to_data_url(args.image_path)
    print("Your image data uri: \n{}".format(data_url))
    create_html_file(data_url, args.output)
