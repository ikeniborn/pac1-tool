"""DSPy optimizer backends (COPRO + GEPA) with shared infrastructure."""
from agent.optimization.base import OptimizerProtocol, CompileResult, BackendError
from agent.optimization.logger import OptimizeLogger

__all__ = ["OptimizerProtocol", "CompileResult", "BackendError", "OptimizeLogger"]
