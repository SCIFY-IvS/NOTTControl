"""H2RG / MACIE camera helpers.

Script acquire (GUI must be open)::

    from nottcontrol.camera.macie.gui_remote import acquire
    acquire()
"""

from nottcontrol.camera.macie.gui_remote import acquire, load_newest

__all__ = ["acquire", "load_newest"]
