from linkmate.core.merge import create_contact, find_matches, merge_into, name_similarity
from linkmate.models import Contact, Note, ProfileDraft


def contact(name, aliases=()):
    return Contact(name=name, aliases=list(aliases))


def test_two_daniels_are_not_the_same_person():
    assert name_similarity("Daniel Kim", "Daniel Schulz") < 0.8


def test_first_name_only_matches_both_daniels_and_the_user_decides():
    contacts = [contact("Daniel Kim"), contact("Daniel Schulz"), contact("Lena Hoffmann")]
    assert {match.name for match in find_matches("Daniel", contacts)} == {"Daniel Kim", "Daniel Schulz"}


def test_aliases_and_titles_match():
    contacts = [contact("Patrick Sullivan", ["Pat"]), contact("Samuel Okafor")]
    assert find_matches("Pat", contacts)[0].name == "Patrick Sullivan"
    assert find_matches("Prof. Okafor", contacts)[0].name == "Samuel Okafor"


def test_typo_still_matches():
    assert find_matches("Lena Hofmann", [contact("Lena Hoffmann")])


def test_merge_newest_value_wins_and_old_value_is_reported():
    first = Note(text="Julia works at Kontora.")
    existing = create_contact(ProfileDraft(name="Julia Brenner", organization="Kontora", skills=["UX design"]), first)
    second = Note(text="Julia moved to Feldwerk.")
    merged, changes = merge_into(existing, ProfileDraft(name="Julia Brenner", organization="Feldwerk"), second)
    assert merged.organization == "Feldwerk"
    assert [(c.field, c.old, c.new) for c in changes] == [("organization", "Kontora", "Feldwerk")]
    assert existing.organization == "Kontora"


def test_merge_empty_value_never_overwrites():
    existing = create_contact(ProfileDraft(name="Julia", role="Designer"), Note(text="a"))
    merged, changes = merge_into(existing, ProfileDraft(name="Julia", role=""), Note(text="b"))
    assert merged.role == "Designer" and not changes


def test_merge_keeps_where_you_first_met():
    existing = create_contact(ProfileDraft(name="Ingrid", met_context="Hardware meetup"), Note(text="a"))
    merged, changes = merge_into(existing, ProfileDraft(name="Ingrid", met_context="Ran into"), Note(text="b"))
    assert merged.met_context == "Hardware meetup" and not changes


def test_merge_fills_empty_where_met():
    existing = create_contact(ProfileDraft(name="Ingrid"), Note(text="a"))
    merged, _ = merge_into(existing, ProfileDraft(name="Ingrid", met_context="Meetup"), Note(text="b"))
    assert merged.met_context == "Meetup"


def test_merge_lists_have_no_duplicates_and_keep_both_sources():
    first, second = Note(text="a"), Note(text="b")
    existing = create_contact(ProfileDraft(name="Tom", skills=["CAD"]), first)
    merged, _ = merge_into(existing, ProfileDraft(name="Tom", skills=["cad", "3D printing"]), second)
    facts = {fact.value: fact.source_note_ids for fact in merged.facts}
    assert facts == {"CAD": [first.id, second.id], "3D printing": [second.id]}


def test_merge_keeps_full_name_and_adds_short_name_as_alias():
    existing = create_contact(ProfileDraft(name="Patrick Sullivan"), Note(text="a"))
    merged, _ = merge_into(existing, ProfileDraft(name="Pat"), Note(text="b"))
    assert merged.name == "Patrick Sullivan" and merged.aliases == ["Pat"]


def test_names_in_any_script_match_and_accents_are_ignored():
    assert name_similarity("李明", "李明") == 1.0
    assert name_similarity("José García", "Jose Garcia") == 1.0
