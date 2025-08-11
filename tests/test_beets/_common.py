def item(**kwargs):
    import beets.library

    default_kwargs = dict(
        title="the title",
        artist="the artist",
        albumartist="the album artist",
        album="the album",
        genre="the genre",
        lyricist="the lyricist",
        composer="the composer",
        arranger="the arranger",
        grouping="the grouping",
        year=1,
        month=2,
        day=3,
        track=4,
        tracktotal=5,
        disc=6,
        disctotal=7,
        lyrics="the lyrics",
        comments="the comments",
    )
    default_kwargs.update(kwargs)

    i = beets.library.Item(
        None,
        **default_kwargs,
    )
    return i
