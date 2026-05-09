import os
import docker


def get_image_size(image_name: str) -> float | None:
    """Get the size of a Docker image in MB. Pulls if not local."""
    try:
        client = docker.from_env()
        try:
            image = client.images.get(image_name)
        except docker.errors.ImageNotFound:
            print(f"Pulling image: {image_name}...")
            image = client.images.pull(image_name)
        size_mb = image.attrs.get('Size', 0) / (1024 * 1024)
        return size_mb
    except Exception:
        return None


DEFAULT_TAG = "slimcraft-build:temp"


def build_image(dockerfile_path: str) -> dict | None:
    """Build a Docker image from a Dockerfile and return image info."""
    df_dir = os.path.dirname(os.path.abspath(dockerfile_path))
    df_name = os.path.basename(dockerfile_path)

    try:
        client = docker.from_env()
        image, logs = client.images.build(
            path=df_dir,
            dockerfile=df_name,
            tag=DEFAULT_TAG,
            rm=True,
            forcerm=True,
        )
        size_mb = image.attrs.get('Size', 0) / (1024 * 1024)
        layers = len(image.attrs.get('RootFS', {}).get('Layers', []))
        client.images.remove(image.id, force=True)
        return {"size_mb": size_mb, "layers": layers}
    except docker.errors.BuildError as e:
        last_log = ""
        for chunk in e.build_log:
            if isinstance(chunk, dict):
                last_log = chunk.get('stream', '') or last_log
        return {"error": f"Build failed: {last_log.strip()[:200]}"}
    except Exception as e:
        return {"error": f"Build error: {e}"}
