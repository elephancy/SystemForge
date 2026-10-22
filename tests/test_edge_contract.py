"""Negative fixtures for the repository's mapped Nginx cache/security contract."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("edge_contract", ROOT / "scripts/edge_contract.py")
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class EdgeContract(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "deploy/nginx.conf").read_text()

    def rejected(self, old, new):
        self.assertIn(old, self.source)
        mutated = self.source.replace(old, new, 1)
        with self.assertRaises(POLICY.ContractError):
            POLICY.check(mutated)

    def test_approved_maps_preserve_route_policy(self):
        POLICY.check(self.source)

    def test_missing_asset_cannot_become_immutable(self):
        self.rejected('~^0:/assets/ "";', '~^0:/assets/ "public, max-age=31536000, immutable";')

    def test_error_status_cannot_become_cacheable(self):
        self.rejected('default 0;', 'default 1;')

    def test_successful_redirect_status_keeps_cache_policy(self):
        self.rejected('307 1; 308 1;', '307 1; 308 0;')

    def test_spa_requires_no_transform(self):
        self.rejected('max-age=0, must-revalidate, no-transform', 'max-age=0, must-revalidate')

    def test_stale_edge_fallback_is_preserved(self):
        self.rejected('stale-if-error=86400', 'stale-if-error=0')

    def test_s_maxage_is_rejected(self):
        self.rejected('public, max-age=300,', 'public, s-maxage=300, max-age=300,')

    def test_location_cannot_shadow_security_headers(self):
        self.rejected('location /assets/ {', 'location /assets/ {\n      add_header X-Test fixture;')

    def test_security_headers_apply_to_error_responses(self):
        self.rejected('add_header X-Content-Type-Options "nosniff" always;', 'add_header X-Content-Type-Options "nosniff";')

    def test_request_uri_must_survive_spa_internal_redirect(self):
        self.rejected('map $request_uri $route_robots_tag', 'map $uri $route_robots_tag')

    def test_unknown_routes_keep_honest_404_status(self):
        self.rejected('error_page 404 =404 /index.html;', 'error_page 404 =200 /index.html;')

    def test_offline_error_page_must_be_internal(self):
        self.rejected('      internal;', '      # internal removed')

    def test_quoted_braces_and_comments_cannot_spoof_header_scope(self):
        parsed = POLICY.directives('http { # }\n map $uri $x { default "{;#}"; } }')
        self.assertEqual(parsed[0][1][0][1][0][0], ('default', '{;#}'))

    def test_literal_delimiters_remain_map_values(self):
        parsed = POLICY.directives('http { map $uri $x { default "{"; other ";"; close "}"; } }')
        self.assertEqual([row for row, _ in parsed[0][1][0][1]],
                         [('default', '{'), ('other', ';'), ('close', '}')])


if __name__ == "__main__":
    unittest.main()
