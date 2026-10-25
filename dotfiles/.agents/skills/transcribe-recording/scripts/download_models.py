"""Download speech models into the Hugging Face cache, one after the other.

Run this file with the Python that Nativ bundles, outside the Bash sandbox, with the
repository names as arguments. The cache (`~/.cache/huggingface/hub`, which Nativ
also reads) is outside the sandbox, and the loader module imports MLX.

A gated repository, like Cohere Transcribe, needs its licence accepted on Hugging Face
and a token. When only Nativ holds the token, in the macOS Keychain, the script asks
the server of Nativ to transcribe one second of silence with that model: the server
downloads the weights with its token. Nativ must be open for this.
"""

from __future__ import annotations

import io
import sys
import time
import urllib.request
import uuid
import wave

from huggingface_hub import snapshot_download
from mlx_audio.utils import get_model_path

SERVER = "http://127.0.0.1:8080/v1/audio/transcriptions"
"""The local transcription endpoint of Nativ."""


def silence() -> bytes:
    """Return one second of silence as a mono 16 kHz WAV file."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 16000)
    return buffer.getvalue()


def through_server(repo: str) -> str:
    """Make the server of Nativ download the model, and return its local path."""
    boundary = uuid.uuid4().hex
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n'
        f"{repo}\r\n--{boundary}\r\nContent-Disposition: form-data;"
        f' name="file"; filename="silence.wav"\r\nContent-Type: audio/wav\r\n\r\n'
    )
    body = head.encode() + silence() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        SERVER,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=3600) as response:
        response.read()
    return str(snapshot_download(repo_id=repo, local_files_only=True))


for repo in sys.argv[1:]:
    start = time.perf_counter()
    try:
        path = get_model_path(repo)
    except Exception as error:  # noqa: BLE001
        # Report the failure, then try the server of Nativ, which holds a token.
        print(f"direct download of {repo} failed: {type(error).__name__}: {error}")
        try:
            path = through_server(repo)
        except Exception as again:  # noqa: BLE001
            print(f"FAILED {repo}: {type(again).__name__}: {again}", flush=True)
            continue
    print(f"READY {repo} in {time.perf_counter() - start:.0f} s at {path}", flush=True)
