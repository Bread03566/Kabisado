import pytest
from app.services.segmenter_service import segmenter_service
from app.services.parser_service import parser_service

def test_segmenter_with_headings():
    sample_text = (
        "Chapter 1: Cell Structure\n"
        "Cells are the basic structural and functional units of every living organism. "
        "The cell membrane encloses the cytoplasm and controls passage of substances.\n\n"
        "Chapter 2: Photosynthesis and Energy\n"
        "Photosynthesis is the biological process used by plants to convert light energy into chemical energy. "
        "Chlorophyll is the green pigment responsible for absorbing sunlight."
    )
    topics = segmenter_service.segment_text(sample_text, document_title="Biology Module")
    assert len(topics) >= 2
    assert "Cell Structure" in topics[0]["title"]
    assert "Photosynthesis" in topics[1]["title"]

PDF_PAGES = [
    "IT2602\n\n05 Handout 1\n*Property of STI\nPage 1 of 3\n\nCONFIGURING NETWORK CONNECTIONS\n"
    "Internet Connection Types\nThe Internet is a global network of networks. The backbone consists of\n"
    "high-bandwidth fiber optic links. Customers connect to the Internet via an ISP�s network.\n"
    "Each connection uses the nearest point of presence, such as a local telephone exchange.",
    "IT2602\n\n05 Handout 1\n*Property of STI\nPage 2 of 3\n\nRole of the Router\n"
    "A router forwards packets between networks. It implements the Internet Protocol and keeps a\n"
    "routing table of known networks. Routers also separate broadcast domains on a local network.\n"
    "�\nHome routers often combine a switch, access point, and modem in one box.",
    "IT2602\n\n05 Handout 1\n*Property of STI\nPage 3 of 3\n\nDomain Name System\n"
    "DNS is a hierarchical system that resolves host names to IP addresses. Clients send queries to a\n"
    "resolver, which contacts root, top-level domain, and authoritative servers in turn until it\n"
    "finds the answer and caches it for later requests.",
]


def test_pdf_cleanup_removes_repeated_headers_and_page_numbers():
    text = parser_service.clean_pdf_pages(PDF_PAGES)
    assert "IT2602" not in text
    assert "Property of STI" not in text
    assert "Page 2 of 3" not in text
    assert "ISP's network" in text
    assert "�" not in text
    assert "Domain Name System" in text


def test_segmenter_ignores_course_codes_and_finds_real_headings():
    text = parser_service.clean_pdf_pages(PDF_PAGES)
    titles = [t["title"] for t in segmenter_service.segment_text(text, document_title="Networking")]
    assert not any("It2602" in t or "IT2602" in t for t in titles)
    assert any("Router" in t for t in titles)
    assert any("Domain Name System" in t for t in titles)


def test_segmenter_caps_topic_count():
    text = "\n\n".join(
        f"Chapter {i}: Topic number {i}\n" + "This sentence fills the section with enough words to count. " * 4
        for i in range(1, 31)
    )
    topics = segmenter_service.segment_text(text, document_title="Long Module")
    assert 2 <= len(topics) <= segmenter_service.MAX_TOPICS
    assert [t["order_index"] for t in topics] == list(range(len(topics)))


def test_plain_text_parser_validation():
    with pytest.raises(Exception):
        parser_service.parse_plain_text("Too short")

    valid_text = "Photosynthesis is the process by which green plants and certain other organisms transform light energy into chemical energy."
    parsed = parser_service.parse_plain_text(valid_text)
    assert len(parsed) > 30


def test_plan_counts_matches_requested_total():
    from app.services.topic_planner import plan_counts

    sizes = [100, 400, 50, 300]
    plan = plan_counts(sizes, 5, size_of=lambda s: s)
    assert sum(n for _, n in plan) == 5
    # More items than topics: everyone gets one, the biggest topic gets the extra
    assert dict(plan) == {100: 1, 400: 2, 50: 1, 300: 1}

    # Fewer items than topics: only the biggest topics are used, in document order
    assert plan_counts(sizes, 2, size_of=lambda s: s) == [(400, 1), (300, 1)]
    assert plan_counts(sizes, 0, size_of=lambda s: s) == []
