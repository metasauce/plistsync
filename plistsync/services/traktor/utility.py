from lxml.etree import _Element


def xpath_string_escape(input_str: str) -> str:
    """Create a concatenation of alternately-quoted strings.

    This is always a valid XPath expression.
    see https://stackoverflow.com/questions/57639667/how-to-deal-with-single-and-double-quotes-in-xpath-in-python
    """
    if "'" not in input_str:
        return f"'{input_str}'"
    parts = input_str.split("'")
    return "concat('" + "', \"'\" , '".join(parts) + "', '')"


def sanitize_plist_name(input_str: str) -> str:
    """Sanitize the playlist name, traktor is picky with special characters."""
    return input_str.replace("$", "*").replace("\\", "|").lstrip("_")


def detach(node: _Element) -> None:
    """Detactch node from parent."""
    parent = node.getparent()
    if parent is not None:
        parent.remove(node)
