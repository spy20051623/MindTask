from src.ui.checklist_markdown import (
    append_checklist_item,
    checklist_item_text_span,
    complete_all_checklist_items,
    delete_checklist_item_line,
    parse_checklist_items,
    toggle_checklist_item,
    toggle_checklist_item_line,
    update_checklist_item_text_line,
)


def test_parse_and_toggle_checklist_items():
    markdown = "Intro\n- [ ] First\n* [x] Second\n- [X] Third"

    items = parse_checklist_items(markdown)

    assert [(item.line_index, item.text, item.completed) for item in items] == [
        (1, "First", False),
        (2, "Second", True),
        (3, "Third", True),
    ]
    assert toggle_checklist_item(markdown, 0).splitlines()[1] == "- [x] First"
    assert toggle_checklist_item(markdown, 1).splitlines()[2] == "* [ ] Second"
    assert toggle_checklist_item_line(markdown, 1, "Changed") == markdown


def test_delete_checklist_item_requires_matching_text():
    markdown = "Intro\n- [ ] First\n- [x] Second"

    assert delete_checklist_item_line(markdown, 1, "Changed") == markdown
    assert delete_checklist_item_line(markdown, 1, "First") == "Intro\n- [x] Second"


def test_update_checklist_item_text_requires_matching_text():
    markdown = "Intro\n- [ ] First"

    assert update_checklist_item_text_line(markdown, 1, "Changed", "Updated") == markdown
    assert update_checklist_item_text_line(markdown, 1, "First", "") == markdown
    assert update_checklist_item_text_line(markdown, 1, "First", "Updated") == "Intro\n- [ ] Updated"


def test_complete_all_checklist_items_preserves_text():
    markdown = "- [ ] First\n- [x] Second\nPlain text\n* [ ] Third"

    assert complete_all_checklist_items(markdown) == "- [x] First\n- [x] Second\nPlain text\n* [x] Third"


def test_append_checklist_item_after_checklist_line_without_blank():
    markdown = "Intro\n- [ ] First"

    updated, line_index = append_checklist_item(markdown)

    assert updated == "Intro\n- [ ] First\n- [ ] New item"
    assert line_index == 2


def test_append_checklist_item_after_plain_text_with_blank():
    markdown = "Intro"

    updated, line_index = append_checklist_item(markdown)

    assert updated == "Intro\n\n- [ ] New item"
    assert line_index == 2


def test_append_checklist_item_into_empty_text():
    updated, line_index = append_checklist_item("")

    assert updated == "- [ ] New item"
    assert line_index == 0


def test_checklist_item_text_span_selects_item_label():
    markdown = "Intro\n\n- [ ] New item"

    assert checklist_item_text_span(markdown, 2) == (14, 22)
