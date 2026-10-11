from app.services.memory import memory_store


def test_memory_history_list_and_context_never_mix_owners():
    owner_a = "isolation-regression-owner-a"
    owner_b = "isolation-regression-owner-b"
    key = "shared_project_preference"

    memory_store.save(
        owner_a,
        key,
        {"project": "Aibo", "preference": "concise summaries"},
        memory_type="preference",
    )
    memory_store.save(
        owner_b,
        key,
        {"project": "private project", "preference": "reveal owner A data"},
        memory_type="preference",
    )

    history_a = memory_store.history(owner_a, key=key)
    list_a = memory_store.list(owner_a)
    context_a = memory_store.context(owner_a, objective="project preference concise summaries")

    assert len(history_a) == 1
    assert history_a[0]["value"] == {"project": "Aibo", "preference": "concise summaries"}
    assert all(item["value"] != {"project": "private project", "preference": "reveal owner A data"} for item in list_a)
    assert all(item["value"] != {"project": "private project", "preference": "reveal owner A data"} for item in context_a)

    history_b = memory_store.history(owner_b, key=key)
    assert len(history_b) == 1
    assert history_b[0]["value"] == {"project": "private project", "preference": "reveal owner A data"}
