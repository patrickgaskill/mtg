"""Browser tests for the single-page report site, using Playwright and Chromium.

The site is generated from the fixture dataset and served locally. The page loads
AG Grid and Tippy from CDNs; set MTG_CDN_MIRROR to a folder of unpacked npm
packages (see `_CDN_FILES`) to serve them locally when offline. Set
CHROMIUM_EXECUTABLE to use a specific browser binary. Without a browser these
tests are skipped, unless MTG_REQUIRE_BROWSER is set (as in CI).
"""

import http.server
import os
import re
import shutil
import threading
from functools import partial
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

from mtg import cli  # noqa: E402
from mtg.aggregators import AGGREGATOR_CLASSES  # noqa: E402
from mtg.config import Paths  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

# CDN URL suffix -> path inside MTG_CDN_MIRROR (unpacked `npm pack` tarballs).
_CDN_FILES = {
    "ag-grid-community@33.2.1/dist/ag-grid-community.min.js": (
        "ag-grid-community-33.2.1/package/dist/ag-grid-community.min.js"
    ),
    "ag-grid-community@33.2.1/styles/ag-grid.css": (
        "ag-grid-community-33.2.1/package/styles/ag-grid.css"
    ),
    "ag-grid-community@33.2.1/styles/ag-theme-quartz.css": (
        "ag-grid-community-33.2.1/package/styles/ag-theme-quartz.css"
    ),
    "@popperjs/core@2.11.8/dist/umd/popper.min.js": (
        "popperjs-core-2.11.8/package/dist/umd/popper.min.js"
    ),
    "tippy.js@6.3.7/dist/tippy.css": "tippy.js-6.3.7/package/dist/tippy.css",
    "tippy.js@6.3.7": "tippy.js-6.3.7/package/dist/tippy-bundle.umd.min.js",
}

# The fixture cards point at a fake image host; failures loading them are expected.
_FAKE_IMAGE_HOST = "https://img.test/"


@pytest.fixture(scope="module")
def site_url(tmp_path_factory):
    paths = Paths(tmp_path_factory.mktemp("spa"))
    paths.types_file.parent.mkdir(parents=True)
    paths.manual.mkdir()
    shutil.copy(FIXTURES / "types.json", paths.types_file)
    shutil.copy(FIXTURES / "supercycles.yaml", paths.supercycles_file)
    site = paths.root / "site"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cli._State, "paths", paths)
        cli.generate(FIXTURES / "sample_cards.jsonl", site)

    handler = partial(QuietHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        pass


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        executable = os.environ.get("CHROMIUM_EXECUTABLE")
        try:
            browser = p.chromium.launch(executable_path=executable or None)
        except Exception as e:
            if os.environ.get("MTG_REQUIRE_BROWSER"):
                raise
            pytest.skip(f"Chromium unavailable: {e}")
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    mirror = os.environ.get("MTG_CDN_MIRROR")
    if mirror:

        def serve_from_mirror(route):
            url = route.request.url
            for suffix, local in _CDN_FILES.items():
                if url.endswith(suffix):
                    return route.fulfill(path=str(Path(mirror) / local))
            return route.abort()

        context.route(re.compile(r"cdn\.jsdelivr\.net|unpkg\.com"), serve_from_mirror)

    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "requestfailed",
        lambda r: None if r.url.startswith(_FAKE_IMAGE_HOST) else errors.append(r.url),
    )
    yield page
    context.close()
    assert errors == [], f"Page errors: {errors}"


def rows(page):
    return page.locator(".ag-center-cols-container .ag-row")


def wait_for_row_count(page, count):
    page.wait_for_function(
        "n => document.querySelectorAll('.ag-center-cols-container .ag-row').length === n",
        arg=count,
    )


def test_home_lists_every_report(page, site_url):
    page.goto(site_url)
    page.wait_for_selector("#report-list li")

    assert page.locator("#report-list li").count() == len(AGGREGATOR_CLASSES)
    assert page.text_content("#generated-at").startswith("Data from Scryfall as of")
    assert page.title() == "MTG Card Data Reports"


def test_report_page(page, site_url):
    page.goto(site_url)
    page.click('#report-list a:text("Cards with the Most Functional Reprints")')
    page.wait_for_selector(".ag-row")

    assert page.url.endswith("#/most_functional_reprints")
    assert page.title() == "Cards with the Most Functional Reprints"
    assert "<strong>functional reprint</strong>" in page.inner_html("#report-explanation")
    assert page.input_value("#nav-select") == "most_functional_reprints"
    link = page.locator(".ag-row a.card-link").first
    assert link.get_attribute("href").startswith("https://scryfall.com/card/")


def test_switching_reports_replaces_the_grid(page, site_url):
    page.goto(site_url + "#/most_functional_reprints")
    page.wait_for_selector(".ag-row")

    page.select_option("#nav-select", "count_cards_by_name")
    page.wait_for_function(
        "document.querySelector('#report-title').textContent === 'Cards by Name'"
    )
    page.wait_for_selector(".ag-row")

    assert page.locator(".ag-root-wrapper").count() == 1
    assert page.is_hidden("#report-explanation")


def test_type_filters_hide_rows_and_persist_in_url(page, site_url):
    page.goto(site_url + "#/maximal_printed_types")
    page.wait_for_selector(".ag-row")
    before = rows(page).count()
    planeswalkers = page.locator("#report-filters label", has_text="Planeswalkers").locator("input")

    planeswalkers.uncheck()
    wait_for_row_count(page, before - 2)

    assert page.url.endswith("#/maximal_printed_types?types%3APlaneswalker=0")
    page.reload()
    page.wait_for_selector(".ag-row")
    assert not planeswalkers.is_checked()
    wait_for_row_count(page, before - 2)


def test_old_report_urls_redirect(page, site_url):
    page.goto(site_url + "maximal_printed_types.html?types:Planeswalker=0")
    page.wait_for_selector(".ag-row")

    assert "index.html#/maximal_printed_types" in page.url
    planeswalkers = page.locator("#report-filters label", has_text="Planeswalkers").locator("input")
    assert not planeswalkers.is_checked()


def test_back_button_returns_home(page, site_url):
    page.goto(site_url + "#/")
    page.wait_for_selector("#home-view:not([hidden])")
    page.goto(site_url + "#/supercycle_completion_time")
    page.wait_for_selector(".ag-row")

    page.go_back()
    page.wait_for_selector("#home-view:not([hidden])")

    assert page.is_hidden("#report-view")


def test_supercycle_rows_link_each_card(page, site_url):
    page.goto(site_url + "#/supercycle_completion_time")
    page.wait_for_selector(".ag-row")

    assert page.locator(".ag-row a.card-link", has_text="Dryad Arbor").count() == 1


def test_unknown_report_shows_error(page, site_url):
    page.goto(site_url + "#/nope")
    page.wait_for_selector("#app-error:not([hidden])")

    assert "Unknown report" in page.text_content("#app-error")


def test_no_horizontal_scroll_on_phones(page, site_url):
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(site_url + "#/first_creature_type_by_color")
    page.wait_for_selector(".ag-row")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0
