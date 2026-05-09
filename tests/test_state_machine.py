import pytest
from core.state_machine import ConversationState, SessionState


def test_default_state_is_idle():
    s = SessionState()
    assert s.state == ConversationState.IDLE


def test_roundtrip_serialisation():
    s = SessionState()
    s.state = ConversationState.VOCAB_QUIZ
    s.pending_vocab_ids = [10, 20, 30]
    s.placement_scores = {"A1": 5, "B1": 3}
    s.current_card_id = 42
    s.word_callbacks = {"水": "the dragon drank from the fountain"}

    d = s.to_dict()
    s2 = SessionState.from_dict(d)

    assert s2.state == ConversationState.VOCAB_QUIZ
    assert s2.pending_vocab_ids == [10, 20, 30]
    assert s2.placement_scores == {"A1": 5, "B1": 3}
    assert s2.current_card_id == 42
    assert s2.word_callbacks == {"水": "the dragon drank from the fountain"}


def test_all_states_are_valid_enum_values():
    for s in ConversationState:
        recovered = ConversationState(s.value)
        assert recovered == s


def test_from_dict_handles_missing_keys():
    s = SessionState.from_dict({})
    assert s.state == ConversationState.IDLE
    assert s.pending_vocab_ids == []
    assert s.placement_scores == {}
