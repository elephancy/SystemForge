"""Check the response-cache contract against Nginx's mapped header policy."""
from pathlib import Path
import re
import sys


SPA = "public, max-age=0, must-revalidate, no-transform"
CDN = "public, max-age=300, stale-while-revalidate=60, stale-if-error=86400"
CASES = [
    ("/health", 200, None, None, None),
    ("/assets/app.js", 200, "public, max-age=31536000, immutable", None, None),
    ("/assets/missing.js", 404, None, None, None),
    ("/manifest.webmanifest", 200, "public, max-age=3600", None, None),
    ("/asset-manifest.json", 200, "no-cache", None, None),
    ("/asset-precache.json", 200, "no-cache", None, None),
    ("/robots.txt", 200, None, None, None),
    ("/sitemap.xml", 200, None, None, None),
    ("/lab", 200, SPA, CDN, None),
    ("/scenario/fixture", 200, SPA, CDN, "noindex, follow"),
    ("/scenario/fixture?mode=view", 200, SPA, CDN, "noindex, follow"),
    ("/scenario/fixture/extra", 404, SPA, CDN, None),
    ("/unknown-route", 404, SPA, CDN, None),
    ("/offline.html", 404, "no-store, no-transform", None, None),
]


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def directives(source):
    """Read this repository's directives, quoted values and nested blocks.

    This is not a replacement for real Nginx syntax/runtime validation. Comments
    and quoted braces cannot masquerade as directives or change block nesting.
    """
    tokens = []
    pattern = re.compile(r'''\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};\"\x27#]+''')
    offset = 0
    for match in pattern.finditer(source):
        require(match.start() == offset, "Unrecognized Nginx configuration token.")
        offset = match.end()
        token = match.group()
        if token.isspace() or token.startswith("#"):
            continue
        quoted = token[0] in ('"', "'")
        if quoted:
            token = token[1:-1]
        tokens.append((token, quoted))
    require(offset == len(source), "Unrecognized Nginx configuration suffix.")
    index = 0

    def block(nested=False):
        nonlocal index
        result = []
        words = []
        while index < len(tokens):
            token, quoted = tokens[index]
            index += 1
            if token == "}" and not quoted:
                require(nested and not words, "Unexpected Nginx closing brace.")
                return result
            if token == "{" and not quoted:
                require(bool(words), "Nginx block requires a directive.")
                result.append((tuple(words), block(True)))
                words = []
            elif token == ";" and not quoted:
                require(bool(words), "Empty Nginx directive.")
                result.append((tuple(words), None))
                words = []
            else:
                words.append(token)
        require(not nested and not words, "Unterminated Nginx directive or block.")
        return result

    return block()


def one_block(nodes, words):
    found = [children for directive, children in nodes if directive == words and children is not None]
    require(len(found) == 1, "A required Nginx policy block is missing or duplicated.")
    return found[0]


def entries(nodes):
    require(all(children is None for _, children in nodes), "A policy map cannot contain nested blocks.")
    return [directive for directive, _ in nodes]


def mapped(rows, value):
    require(all(len(row) == 2 for row in rows), "A cache-policy map entry is malformed.")
    exact = [result for key, result in rows if key == value]
    if exact:
        require(len(exact) == 1, "A cache-policy key is duplicated.")
        return exact[0]
    # Nginx checks exact keys before regex entries, irrespective of file order.
    for key, result in rows:
        if key.startswith("~"):
            insensitive = key.startswith("~*")
            expression = key[2:] if insensitive else key[1:]
            if re.search(expression, value, re.IGNORECASE if insensitive else 0):
                return result
    defaults = [result for key, result in rows if key == "default"]
    require(len(defaults) == 1, "A cache-policy map requires exactly one default.")
    return defaults[0]


def check(source):
    tree = directives(source)
    http = one_block(tree, ("http",))
    status = entries(one_block(http, ("map", "$status", "$cacheable_response")))
    cache = entries(one_block(http, ("map", "$cacheable_response:$uri", "$route_cache_control")))
    cdn = entries(one_block(http, ("map", "$uri", "$route_cdn_cache_control")))
    robots = entries(one_block(http, ("map", "$request_uri", "$route_robots_tag")))
    successful_cache_statuses = {200, 201, 204, 206, 301, 302, 303, 304, 307, 308}
    for code in range(200, 600):
        require(mapped(status, str(code)) == ("1" if code in successful_cache_statuses else "0"),
                "Cacheability must match Nginx's successful-response header status set.")
    server = one_block(http, ("server",))
    required_headers = {
        ("add_header", "Cache-Control", "$route_cache_control", "always"),
        ("add_header", "Cloudflare-CDN-Cache-Control", "$route_cdn_cache_control", "always"),
        ("add_header", "X-Robots-Tag", "$route_robots_tag", "always"),
        ("add_header", "X-Content-Type-Options", "nosniff", "always"),
        ("add_header", "Referrer-Policy", "strict-origin-when-cross-origin", "always"),
    }
    headers = [directive for directive, _ in server if directive[0] == "add_header"]
    require(set(headers) == required_headers and len(headers) == len(required_headers),
            "Cache and security headers must be declared exactly once at server scope.")

    def forbid_shadowing(nodes):
        for directive, children in nodes:
            require(directive[0] != "add_header", "Location headers must not shadow server security headers.")
            if children is not None:
                forbid_shadowing(children)

    for _, children in server:
        if children is not None:
            forbid_shadowing(children)
    require(not any("s-maxage=" in word for row in cache + cdn for word in row),
            "s-maxage disables the intended stale edge fallback.")
    require(("try_files", "$uri", "=404") in entries(one_block(server, ("location", "/assets/"))),
            "Missing assets must retain a real 404.")
    fallback = entries(one_block(server, ("location", "/")))
    require(("error_page", "404", "=404", "/index.html") in fallback,
            "Unknown routes must retain a real 404 while rendering the SPA shell.")
    require(("try_files", "$uri", "$uri/", "=404") in fallback,
            "Unknown routes must not become successful SPA responses.")
    for route in ("^/(lab|custom|interview|replay|decisions)$", "^/scenario/[A-Za-z0-9-]+$"):
        require(("try_files", "/index.html", "=404") in entries(one_block(server, ("location", "~", route))),
                "Named SPA routes require the application shell and an honest missing-shell 404.")
    require(("internal",) in entries(one_block(server, ("location", "=", "/offline.html"))),
            "The offline error page must remain internal.")

    for request, code, expected_cache, expected_cdn, expected_robots in CASES:
        uri = request.split("?", 1)[0]
        # SPA fallbacks change $uri; X-Robots-Tag must use the original request.
        internal_uri = "/index.html" if uri.startswith("/scenario/") or uri in ("/lab", "/unknown-route") else uri
        values = (mapped(cache, mapped(status, str(code)) + ":" + internal_uri),
                  mapped(cdn, internal_uri), mapped(robots, request))
        expected = (expected_cache or "", expected_cdn or "", expected_robots or "")
        require(values == expected, "A route's status/cache/CDN/robots policy does not meet the contract.")

    for uri in ("/assets/app.js", "/manifest.webmanifest", "/asset-manifest.json", "/asset-precache.json"):
        for code in (400, 403, 404, 500):
            require(mapped(cache, mapped(status, str(code)) + ":" + uri) == "",
                    "Failed asset responses must not acquire successful-file caching.")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1] if len(sys.argv) > 1 else "deploy/nginx.conf").read_text())
    except (ContractError, OSError, re.error) as error:
        print("Static response cache contract failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    print("Static response cache contract passed (14 route cases and failed-asset cache checks).")
