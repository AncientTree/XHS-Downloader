from source.expansion import Namespace
from .request import Html

__all__ = ["Video"]


class Video:
    VIDEO_LINK = (
        "video",
        "consumer",
        "originVideoKey",
    )

    @classmethod
    def generate_video_link(cls, data: Namespace) -> list:
        return (
            [Html.format_url(f"https://sns-video-bd.xhscdn.com/{t}")]
            if (t := data.safe_extract(".".join(cls.VIDEO_LINK)))
            else []
        )

    @classmethod
    def get_video_link(
        cls,
        data: Namespace,
        preference="resolution",
    ) -> list:
        if not (items := cls.get_video_items(data)):
            return []
        match preference:
            case "resolution":
                items.sort(key=lambda x: x.height)
            case "bitrate" | "size":
                items.sort(key=lambda x: x.preference)
            case _:
                raise ValueError(f"Invalid video preference value: {preference}")
        return [b[0]] if (b := items[-1].backupUrls) else [items[-1].masterUrl]

    @staticmethod
    def get_video_items(data: Namespace) -> list:
        h264 = data.safe_extract("video.media.stream.h264")
        h265 = data.safe_extract("video.media.stream.h265")
        return [*h264, *h265]
