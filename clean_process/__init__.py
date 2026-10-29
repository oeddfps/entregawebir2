"""Clean&Process: source-independent, evidence-backed content processing."""
from .contracts import Input, Output
from .processor import process

__all__ = ['Input', 'Output', 'process']
