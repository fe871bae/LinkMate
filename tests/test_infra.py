from conftest import fake_embed

from linkmate.infra.index import ChromaIndex
from linkmate.infra.ollama_client import EMBED_BATCH, OllamaClient
from linkmate.infra.store import ContactStore
from linkmate.models import Contact, Note


def lena() -> Contact:
    return Contact(name="Lena", notes=[Note(text="Calibrates IMU sensors")])


def test_contact_file_with_invalid_encoding_is_listed_as_corrupt(tmp_path):
    store = ContactStore(tmp_path)
    store.save(lena())
    (tmp_path / "c_broken.json").write_bytes(b"\xff\xfe")
    contacts, corrupt = store.load_all()
    assert len(contacts) == 1 and corrupt == ["c_broken.json"]
    assert store.get("broken") is None


def test_damaged_index_file_does_not_block_opening_or_rebuild(tmp_path):
    path = tmp_path / "chroma"
    path.mkdir()
    (path / "chroma.sqlite3").write_bytes(b"this is not a database")
    index = ChromaIndex(path, fake_embed)
    index.rebuild([lena()])
    assert len(index.entry_ids()) == 2


def test_scores_are_cosine_similarity(tmp_path):
    index = ChromaIndex(tmp_path / "chroma", fake_embed)
    contact = lena()
    index.upsert_contact(contact)
    best = max(index.query("Calibrates IMU sensors", 5), key=lambda hit: hit.score)
    assert best.entry.doc_type == "note" and best.score > 0.99


def test_rebuild_removes_entries_that_could_not_be_deleted_with_the_folder(tmp_path, monkeypatch):
    # On Windows the folder of an open database cannot be deleted.
    index = ChromaIndex(tmp_path / "chroma", fake_embed)
    old = lena()
    index.upsert_contact(old)
    monkeypatch.setattr(index, "_reset_folder", lambda: None)
    new = Contact(name="Tom", notes=[Note(text="Prints parts")])
    index.rebuild([new])
    assert index.entry_ids() == {f"{new.id}:profile", f"{new.notes[0].id}:0"}


def test_embed_splits_large_requests_into_batches(monkeypatch):
    client = OllamaClient("http://localhost:9", "chat", "embed")
    sizes = []

    def post(path, body, model):
        sizes.append(len(body["input"]))
        return {"embeddings": [[0.0] for _ in body["input"]]}

    monkeypatch.setattr(client, "_post", post)
    assert len(client.embed(["x"] * (EMBED_BATCH + 1))) == EMBED_BATCH + 1
    assert sizes == [EMBED_BATCH, 1]
