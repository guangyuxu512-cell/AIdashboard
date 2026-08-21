from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationMessage:
    title: str
    lines: tuple[str, ...]

    def render_text(self) -> str:
        return "\n".join((self.title, "", *self.lines))
