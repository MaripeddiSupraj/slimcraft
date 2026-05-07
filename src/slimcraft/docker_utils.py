import docker


def get_image_size(image_name: str) -> float | None:
    """Get the size of a Docker image in MB. Pulls if not local."""
    try:
        client = docker.from_env()
        try:
            image = client.images.get(image_name)
        except docker.errors.ImageNotFound:
            image = client.images.pull(image_name)
        size_mb = image.attrs.get('Size', 0) / (1024 * 1024)
        return size_mb
    except Exception:
        return None
