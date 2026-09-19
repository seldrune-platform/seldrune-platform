"""Gate ONNX export on verified successful GPU training evidence."""
from services.live_media.face_gpu_receipt import GpuExecutionState, GpuTrainingReceipt


def require_exportable_training(receipt: GpuTrainingReceipt) -> str:
    receipt.validate()
    if receipt.state is not GpuExecutionState.SUCCEEDED:
        raise ValueError("ONNX export requires successful GPU training")
    if not receipt.checkpoint_sha256:
        raise ValueError("ONNX export requires checkpoint evidence")
    return receipt.checkpoint_sha256[-1]
