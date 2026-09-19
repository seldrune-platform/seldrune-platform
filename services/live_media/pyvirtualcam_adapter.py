"""Optional desktop virtual-camera sink backed by pyvirtualcam.

This adapter belongs on a desktop/companion host that exposes an OS virtual
camera. Importing this module does not require pyvirtualcam; the dependency is
loaded only when a sink is opened.
"""

from __future__ import annotations

from typing import Any


class PyVirtualCameraSink:
    def __init__(self, width: int = 256, height: int = 256, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self._camera: Any | None = None

    @property
    def connected(self) -> bool:
        return self._camera is not None

    def open(self) -> PyVirtualCameraSink:
        try:
            import pyvirtualcam
        except ImportError as exc:
            raise RuntimeError(
                "pyvirtualcam is required on the desktop delivery host"
            ) from exc
        self._camera = pyvirtualcam.Camera(
            width=self.width,
            height=self.height,
            fps=self.fps,
        )
        return self

    async def send(self, frame: object) -> None:
        if self._camera is None:
            raise RuntimeError("virtual camera is not open")
        self._camera.send(frame)
        self._camera.sleep_until_next_frame()

    def close(self) -> None:
        camera = self._camera
        self._camera = None
        if camera is not None:
            camera.close()

    def __enter__(self) -> PyVirtualCameraSink:
        return self.open()

    def __exit__(self, *_: object) -> None:
        self.close()
