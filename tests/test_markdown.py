"""Unit tests for the markdown sanitize pipeline (the app's trust boundary)."""

from saathi.services.markdown import (
    NH3_ATTRS,
    NH3_SCHEMES,
    NH3_TAGS,
    _md,
    excerpt,
    highlight,
    render_md,
    sanitize_html,
)


def test_markdown_it_instance_has_html_disabled():
    assert _md.options["html"] is False


def test_raw_html_is_escaped_to_visible_text():
    out = str(render_md("<b>hi</b>"))

    assert "&lt;b&gt;hi&lt;/b&gt;" in out


def test_script_payload_renders_inert():
    out = str(render_md("<script>alert(1)</script>"))

    assert "&lt;script&gt;" in out
    assert "<script" not in out


def test_javascript_link_never_becomes_a_href():
    out = str(render_md("[x](javascript:alert(1))"))

    # markdown-it rejects the scheme outright: the syntax stays literal text,
    # so no anchor (let alone an href) is ever emitted.
    assert "<a" not in out
    assert 'href="javascript:' not in out
    assert "javascript:alert(1)" in out


def test_https_links_carry_noopener_noreferrer():
    out = str(render_md("[docs](https://example.com/a)"))

    assert '<a href="https://example.com/a"' in out
    assert 'rel="noopener noreferrer"' in out


def test_nh3_allowlist_strips_stray_elements_but_keeps_text():
    assert sanitize_html("<div onclick='x'>t</div><iframe></iframe>") == "t"


def test_attributes_outside_allowlist_are_stripped():
    assert sanitize_html('<p id="x" class="y" style="color:red">t</p>') == "<p>t</p>"


def test_img_keeps_only_allowlisted_attributes():
    out = sanitize_html('<img src="https://e/x.png" alt="a" title="t" onerror="evil()">')

    assert 'src="https://e/x.png"' in out
    assert 'alt="a"' in out
    assert "onerror" not in out


def test_data_uri_src_is_dropped_entirely():
    out = sanitize_html('<img src="data:text/html;base64,PHNjcmlwdD4=">')

    assert "src=" not in out


def test_mailto_links_survive():
    out = sanitize_html('<a href="mailto:a@b.c">m</a>')

    assert 'href="mailto:a@b.c"' in out


def test_tables_and_strikethrough_render():
    out = str(render_md("| a |\n| - |\n| b |\n\n~~gone~~"))

    assert "<table>" in out
    assert "<s>gone</s>" in out


def test_single_newline_becomes_br_for_note_taking():
    out = str(render_md("one\ntwo"))

    assert "<br" in out


def test_empty_body_renders_empty_string():
    assert str(render_md("")) == ""
    assert str(render_md(None)) == ""  # type: ignore[arg-type]


def test_excerpt_strips_all_markup():
    assert excerpt("**Bold** _x_\n\npara") == "Bold x para"


def test_excerpt_truncates_on_word_boundary_with_ellipsis():
    out = excerpt("word " * 60)

    assert out.endswith("…")
    assert len(out) <= 161
    assert not out.endswith(" …")


def test_short_content_passes_through_untruncated():
    assert excerpt("tiny note") == "tiny note"


def test_highlight_marks_matches_case_insensitively():
    assert str(highlight("Boost the boost", "boost")) == (
        "<mark>Boost</mark> the <mark>boost</mark>"
    )


def test_highlight_never_smuggles_markup_through_term_or_text():
    assert str(highlight("<img src=x>", "<b>")) == "&lt;img src=x&gt;"


def test_empty_search_term_returns_escaped_plain():
    assert str(highlight("plain & simple", "")) == "plain &amp; simple"


def test_policy_constants_match_the_pinned_contract():
    assert {"del", "s"} <= NH3_TAGS
    assert "script" not in NH3_TAGS
    assert "iframe" not in NH3_TAGS
    assert NH3_ATTRS["*"] == set()
    assert NH3_ATTRS["a"] == {"href", "title"}
    assert "javascript" not in NH3_SCHEMES
