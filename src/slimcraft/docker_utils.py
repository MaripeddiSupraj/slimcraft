import docker

def get_image_size(image_name: str) -> float:
    """
    Attempts to get the size of the image in MB.
    Pulls the image if it is not present locally.
    """
    try:
        client = docker.from_env()
        try:
            image = client.images.get(image_name)
        except docker.errors.ImageNotFound:
            # For a basic scan, we might not want to pull large images automatically
            # but for the base image we can try to inspect the manifest or pull it
            # To keep it fast, we will try to pull it.
            image = client.images.pull(image_name)
            
        # Size in bytes to MB
        size_mb = image.attrs.get('Size', 0) / (1024 * 1024)
        return size_mb
    except Exception:
        # Docker not running or permission denied
        return None
