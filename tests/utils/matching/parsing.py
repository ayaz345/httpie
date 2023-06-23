import re
from typing import Iterable

from httpie.output.writer import MESSAGE_SEPARATOR
from .tokens import Expect
from ...utils import CRLF


SEPARATOR_RE = re.compile(f'^{MESSAGE_SEPARATOR}')
KEY_VALUE_RE = re.compile(r'[\n]*((.*?):(.+)[\n]?)+[\n]*')


def make_headers_re(message_type: Expect):
    assert message_type in {Expect.REQUEST_HEADERS, Expect.RESPONSE_HEADERS}

    # language=RegExp
    crlf = r'[\r][\n]'
    non_crlf = rf'[^{CRLF}]'

    # language=RegExp
    http_version = r'HTTP/\d+\.\d+'
    if message_type is Expect.REQUEST_HEADERS:
        # POST /post HTTP/1.1
        start_line_re = fr'{non_crlf}*{http_version}{crlf}'
    else:
        # HTTP/1.1 200 OK
        start_line_re = fr'{http_version}{non_crlf}*{crlf}'

    return re.compile(
        fr'''
            ^
            {start_line_re}
            ({non_crlf}+:{non_crlf}+{crlf})+
            {crlf}
        ''',
        flags=re.VERBOSE
    )


BODY_ENDINGS = [
    MESSAGE_SEPARATOR,
    CRLF,  # Not really but useful for testing (just remember not to include it in a body).
]
TOKEN_REGEX_MAP = {
    Expect.REQUEST_HEADERS: make_headers_re(Expect.REQUEST_HEADERS),
    Expect.RESPONSE_HEADERS: make_headers_re(Expect.RESPONSE_HEADERS),
    Expect.RESPONSE_META: KEY_VALUE_RE,
    Expect.SEPARATOR: SEPARATOR_RE,
}


class OutputMatchingError(ValueError):
    pass


def expect_tokens(tokens: Iterable[Expect], s: str):
    for token in tokens:
        s = expect_token(token, s)
    if s:
        raise OutputMatchingError(f'Unmatched remaining output for {tokens} in {s!r}')


def expect_token(token: Expect, s: str) -> str:
    return expect_body(s) if token is Expect.BODY else expect_regex(token, s)


def expect_regex(token: Expect, s: str) -> str:
    if match := TOKEN_REGEX_MAP[token].match(s):
        return s[match.end():]
    else:
        raise OutputMatchingError(f'No match for {token} in {s!r}')


def expect_body(s: str) -> str:
    """
    We require some text, and continue to read until we find an ending or until the end of the string.

    """
    if 'content-disposition:' in s.lower():
        # Multipart body heuristic.
        final_boundary_re = re.compile('\r\n--[^-]+?--\r\n')
        if match := final_boundary_re.search(s):
            return s[match.end():]

    if endings := [s.index(sep) for sep in BODY_ENDINGS if sep in s]:
        end = min(endings)
        if end == 0:
            raise OutputMatchingError(f'Empty body: {s!r}')
        return s[end:]
    else:
        return ''
