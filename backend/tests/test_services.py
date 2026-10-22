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

def test_plain_text_parser_validation():
    with pytest.raises(Exception):
        parser_service.parse_plain_text("Too short")

    valid_text = "Photosynthesis is the process by which green plants and certain other organisms transform light energy into chemical energy."
    parsed = parser_service.parse_plain_text(valid_text)
    assert len(parsed) > 30
