"""Backward-compatible entry point for the H2RG GUI."""

from nottcontrol.camera.macie.h2rg_gui import H2rgMainWindow as MacieControl

__all__ = ["MacieControl"]
