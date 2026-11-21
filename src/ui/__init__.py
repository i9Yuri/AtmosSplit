"""Widgets do estúdio. Os processos de render podem iniciar sem carregar o Qt."""

__all__ = ["RoomView714", "StemControlCard"]


def __getattr__(name: str):
    if name == "RoomView714":
        from .room_view_714 import RoomView714
        return RoomView714
    if name == "StemControlCard":
        from .stem_card import StemControlCard
        return StemControlCard
    raise AttributeError(name)
