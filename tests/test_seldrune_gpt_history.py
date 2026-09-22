from backend.app.api.routes.seldrune_gpt import SeldruneGPTHistoryMessage


def test_gpt_history_message_schema():
    message = SeldruneGPTHistoryMessage(
        role="assistant", content="Saved response", model="gpt-test"
    )
    assert message.role == "assistant"
    assert message.content == "Saved response"
    assert message.model == "gpt-test"
