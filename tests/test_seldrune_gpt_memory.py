from backend.app.models.seldrune_gpt_conversation import SeldruneGPTConversation\nfrom backend.app.models.seldrune_gpt_message import SeldruneGPTMessage


def test_gpt_message_model_tracks_conversation_fields():
    message = SeldruneGPTMessage(
        organization_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        role="user",
        content="Remember this project.",
    )
    assert message.role == "user"
    assert message.content == "Remember this project."


def test_gpt_conversations_keep_owner_scope_and_title() -> None:
    conversation = SeldruneGPTConversation(
        organization_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        title="Review deployment",
    )
    assert conversation.organization_id == "00000000-0000-0000-0000-000000000001"
    assert conversation.user_id == "00000000-0000-0000-0000-000000000002"
    assert conversation.title == "Review deployment"
