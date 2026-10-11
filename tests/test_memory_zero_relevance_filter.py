from app.services.memory import memory_store


def test_objective_context_excludes_zero_relevance_memories():
    owner_id = "zero-relevance-context-regression-owner"

    memory_store.save(
        owner_id,
        "preferred_console",
        {"console": "Nintendo Switch", "preference": "handheld games"},
        memory_type="preference",
    )
    memory_store.save(
        owner_id,
        "favorite_pet",
        {"animal": "cat", "color": "orange"},
        memory_type="fact",
    )

    relevant = memory_store.context(owner_id, objective="Nintendo Switch handheld")
    assert len(relevant) == 1
    assert relevant[0]["key"] == "preferred_console"

    no_match = memory_store.context(owner_id, objective="quantum entanglement")
    assert no_match == []
