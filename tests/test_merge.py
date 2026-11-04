from linkmate.core.merge import additive_draft, combine_summary, create_contact, find_matches, merge_into, name_similarity
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


def known_contact():
    note = Note(id="n_1", text="Jonas Keller, firmware engineer at Brightcell.")
    contact = create_contact(
        ProfileDraft(
            name="Jonas Keller", organization="Brightcell", role="firmware engineer", location="Long Beach",
            met_context="embedded night", summary="Firmware engineer at Brightcell.", skills=["STM32"],
            offers_help=["debug firmware"],
        ),
        note,
    )
    return contact


def test_side_note_keeps_everything_known_and_only_adds():
    contact = known_contact()
    side_note = ProfileDraft(name="Jonas Keller", summary="Jonas Keller likes fishing.", interests=["fishing"])
    merged, changes = merge_into(contact, side_note, Note(id="n_2", text="Jonas Keller likes fishing"))
    assert (merged.organization, merged.role, merged.location) == ("Brightcell", "firmware engineer", "Long Beach")
    assert merged.summary == "Firmware engineer at Brightcell. Jonas Keller likes fishing."
    assert merged.values_of("skill") == ["STM32"] and merged.values_of("interest") == ["fishing"]
    assert [note.id for note in merged.notes] == ["n_1", "n_2"] and changes == []


def test_review_form_keeps_known_values_and_lists_only_new_facts():
    contact = known_contact()
    note = ProfileDraft(name="Jonas", role="angler", location="", summary="Likes fishing.", skills=["STM32"], interests=["fishing"])
    draft = additive_draft(contact, note)
    assert (draft.name, draft.role, draft.location) == ("Jonas Keller", "firmware engineer", "Long Beach")
    assert draft.summary == "Firmware engineer at Brightcell. Likes fishing."
    assert draft.skills == [] and draft.interests == ["fishing"] and draft.aliases == ["Jonas"]


def test_confirming_the_review_links_only_new_facts_to_the_new_note():
    contact = known_contact()
    draft = additive_draft(contact, ProfileDraft(name="Jonas Keller", skills=["STM32"], interests=["fishing"]))
    merged, _ = merge_into(contact, draft, Note(id="n_2", text="likes fishing"))
    sources = {fact.value: fact.source_note_ids for fact in merged.facts}
    assert sources["STM32"] == ["n_1"] and sources["fishing"] == ["n_2"]


def test_summary_is_not_duplicated():
    assert combine_summary("Likes fishing.", "Likes fishing.") == "Likes fishing."
    assert combine_summary("Likes fishing.", "Likes fishing. Runs too.") == "Likes fishing. Runs too."
    assert combine_summary("", "New.") == "New." and combine_summary("Old.", "") == "Old."
