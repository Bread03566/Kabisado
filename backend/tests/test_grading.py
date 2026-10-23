from types import SimpleNamespace

from app.services.grading import grade, normalize


def question(question_type, **kw):
    defaults = dict(choices=[], correct_index=0, answer_data=None)
    return SimpleNamespace(question_type=question_type, **{**defaults, **kw})


def test_normalize_ignores_case_punctuation_and_leading_articles():
    assert normalize("  The Propaganda Movement! ") == "propaganda movement"
    assert normalize("an Ilustrado.") == "ilustrado"


def test_identification_accepts_alternates_and_small_typos():
    q = question("identification", answer_data={"answer": "Mitochondria", "accepted_answers": ["powerhouse of the cell"]})
    assert grade(q, text_answer="mitochondria")
    assert grade(q, text_answer="Mitochondira")          # transposed letters
    assert grade(q, text_answer="the powerhouse of the cell")
    assert not grade(q, text_answer="chloroplast")
    assert not grade(q, text_answer="")
    assert not grade(q, text_answer=None)


def test_identification_short_answers_must_match_exactly():
    q = question("identification", answer_data={"answer": "DNS", "accepted_answers": []})
    assert grade(q, text_answer="dns")
    assert not grade(q, text_answer="DHCP")
    assert not grade(q, text_answer="DNA")


def test_matching_needs_every_pair_in_place():
    q = question("matching", answer_data={"pairs": [{"term": "A", "definition": "a"}, {"term": "B", "definition": "b"}, {"term": "C", "definition": "c"}]})
    assert grade(q, matching=[0, 1, 2])
    assert not grade(q, matching=[1, 0, 2])
    assert not grade(q, matching=[0, 1])
    assert not grade(q, matching=None)


def test_choice_questions_compare_the_index():
    mc = question("multiple_choice", choices=["w", "x", "y", "z"], correct_index=2)
    assert grade(mc, selected_index=2)
    assert not grade(mc, selected_index=1)
    assert not grade(mc, selected_index=None)
    tf = question("true_false", choices=["True", "False"], correct_index=1)
    assert grade(tf, selected_index=1)
