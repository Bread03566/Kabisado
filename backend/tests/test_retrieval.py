import asyncio

from app.services.ai_service import AIService
from app.services.retrieval import build_chunks, rank, stem, tokens

TOPICS = [
    {"id": 1, "title": "Photosynthesis", "content": (
        "Photosynthesis is the process by which plants convert light energy into chemical energy. "
        "Chlorophyll is the green pigment that absorbs sunlight in the leaves. "
        "Glucose is the sugar produced during photosynthesis, and oxygen is released as a by-product. "
        "The light reactions happen in the thylakoid membranes of the chloroplast.")},
    {"id": 2, "title": "Cellular Respiration", "content": (
        "Cellular respiration releases the energy stored in glucose so cells can use it. "
        "Mitochondria are the organelles where most ATP is produced. "
        "Glycolysis is the first stage and takes place in the cytoplasm of the cell. "
        "Oxygen is required for the final stage, called the electron transport chain.")},
    {"id": 3, "title": "Genetics", "content": (
        "A gene is a segment of DNA that carries the instructions for one trait. "
        "Alleles are different versions of the same gene. "
        "A dominant allele hides the effect of a recessive allele in a heterozygous organism.")},
]


def top(question, history=None):
    results = rank(build_chunks(TOPICS), question, history=history)
    return results[0][1] if results else None


def test_light_stemming_matches_plurals_and_endings():
    assert stem("plants") == stem("plant")
    assert stem("producing") == stem("produced") == stem("produces")
    assert stem("glucose") == stem("glucoses")
    assert "the" not in tokens("What is the pigment?")


def test_chunks_carry_their_topic_and_a_position_for_citation():
    chunks = build_chunks(TOPICS)
    assert {c.topic_title for c in chunks} == {"Photosynthesis", "Cellular Respiration", "Genetics"}
    first = [c for c in chunks if c.topic_title == "Photosynthesis"]
    assert [c.ordinal for c in first] == list(range(1, len(first) + 1))
    assert all(len(c.text) > 30 for c in chunks)


def test_the_most_relevant_passage_ranks_first():
    assert top("What does chlorophyll do?").topic_title == "Photosynthesis"
    assert "chlorophyll" in top("What does chlorophyll do?").text.lower()
    assert top("Where is ATP made?").topic_title == "Cellular Respiration"
    assert top("What is an allele?").topic_title == "Genetics"


def test_rare_words_outweigh_words_that_appear_everywhere():
    # "glucose" appears in two topics; "thylakoid" in one: the rarer term decides.
    assert top("glucose thylakoid").topic_title == "Photosynthesis"


def test_plurals_and_tenses_still_match():
    assert top("Which organelles produce ATP?").topic_title == "Cellular Respiration"
    assert top("Why do plants need sunlight?").topic_title == "Photosynthesis"


def test_a_question_the_material_cannot_answer_returns_nothing():
    assert rank(build_chunks(TOPICS), "Explain quantum chromodynamics and gluons") == []
    assert rank(build_chunks(TOPICS), "What is the capital of France?") == []
    assert rank(build_chunks(TOPICS), "the of and") == []
    assert rank(build_chunks(TOPICS), "") == []
    assert rank([], "chlorophyll") == []


def test_a_short_follow_up_uses_the_previous_question_for_context():
    history = [{"role": "user", "content": "Tell me about chlorophyll"},
               {"role": "assistant", "content": "It absorbs sunlight."}]
    assert top("Where is it found?", history=history).topic_title == "Photosynthesis"


def test_offline_chat_cites_the_source_and_admits_when_it_does_not_know():
    svc = AIService()
    found = asyncio.run(svc.answer_document_question("Bio", TOPICS, "What does chlorophyll do?"))
    assert found["found_in_document"] is True and "Photosynthesis" in found["citation"]
    assert "absorbs sunlight" in found["answer"]
    missing = asyncio.run(svc.answer_document_question("Bio", TOPICS, "Who won the 1998 World Cup?"))
    assert missing["found_in_document"] is False and missing["citation"] is None


def test_offline_chat_understands_a_short_follow_up_question():
    svc = AIService()
    history = [{"role": "user", "content": "Tell me about chlorophyll"},
               {"role": "assistant", "content": "It absorbs sunlight."}]
    reply = asyncio.run(svc.answer_document_question(
        "Bio", TOPICS, "Where is it found?", conversation_history=history))
    assert reply["found_in_document"] is True and "Photosynthesis" in reply["citation"]


def test_offline_chat_ranks_by_rarity_not_by_raw_word_hits():
    topics = [{"id": 1, "title": "Cells", "content": (
        "The cell is the basic unit of life and every cell has a membrane around the cell. "
        "A cell uses energy and a cell can divide to make a new cell. "
        "The nucleus stores DNA and directs the activities of the cell.")}]
    reply = asyncio.run(AIService().answer_document_question("Bio", topics, "What does the nucleus store?"))
    assert "nucleus stores DNA" in reply["answer"]
