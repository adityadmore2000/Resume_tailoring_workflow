from __future__ import annotations


class ResumeTreeError(Exception):
    pass


class NotFoundError(ResumeTreeError):
    pass


class InvalidOperationError(ResumeTreeError):
    pass


class CycleError(InvalidOperationError):
    pass

