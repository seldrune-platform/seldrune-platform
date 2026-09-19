"""Provider-neutral architecture contract for Seldrune Face v0.1."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceArchitecture:
    version: str = "seldrune-face-arch-v0.1"
    input_channels: int = 3
    identity_embedding_dim: int = 512
    encoder_width: int = 64
    bottleneck_width: int = 512
    decoder_width: int = 64
    output_channels: int = 3

    def validate(self) -> None:
        if self.input_channels != 3 or self.output_channels != 3:
            raise ValueError("Face v0.1 requires RGB input and output")
        if self.identity_embedding_dim < 128:
            raise ValueError("identity embedding is too small")
        for name, width in (
            ("encoder_width", self.encoder_width),
            ("bottleneck_width", self.bottleneck_width),
            ("decoder_width", self.decoder_width),
        ):
            if width < 1:
                raise ValueError(f"{name} must be positive")


def default_face_architecture() -> FaceArchitecture:
    architecture = FaceArchitecture()
    architecture.validate()
    return architecture
