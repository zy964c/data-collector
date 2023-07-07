def get_image(image):
    with open(image, "rb") as f:
        return f.read()
