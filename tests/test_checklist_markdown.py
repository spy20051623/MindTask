from src.ui.tasks.checklist_markdown import ChecklistMarkdown


def test_parse_and_toggle_checklist_items():
    markdown = "Intro\n- [ ] First\n* [x] Second\n- [X] Third"
    checklist = ChecklistMarkdown(markdown)

    items = checklist.items()

    assert [(item.line_index, item.text, item.completed) for item in items] == [
        (1, "First", False),
        (2, "Second", True),
        (3, "Third", True),
    ]
    assert checklist.toggle_item(0).splitlines()[1] == "- [x] First"
    assert checklist.toggle_item(1).splitlines()[2] == "* [ ] Second"
    assert checklist.toggle_line(1, "Changed") == markdown


def test_delete_checklist_item_requires_matching_text():
    markdown = "Intro\n- [ ] First\n- [x] Second"
    checklist = ChecklistMarkdown(markdown)

    assert checklist.delete_line(1, "Changed") == markdown
    assert checklist.delete_line(1, "First") == "Intro\n- [x] Second"


def test_update_checklist_item_text_requires_matching_text():
    markdown = "Intro\n- [ ] First"
    checklist = ChecklistMarkdown(markdown)

    assert checklist.update_text(1, "Changed", "Updated") == markdown
    assert checklist.update_text(1, "First", "") == markdown
    assert checklist.update_text(1, "First", "Updated") == "Intro\n- [ ] Updated"


def test_complete_all_checklist_items_preserves_text():
    markdown = "- [ ] First\n- [x] Second\nPlain text\n* [ ] Third"

    assert ChecklistMarkdown(markdown).complete_all() == "- [x] First\n- [x] Second\nPlain text\n* [x] Third"


def test_append_checklist_item_after_checklist_line_without_blank():
    markdown = "Intro\n- [ ] First"

    updated, line_index = ChecklistMarkdown(markdown).append_item()

    assert updated == "Intro\n- [ ] First\n- [ ] New item"
    assert line_index == 2


def test_append_checklist_item_after_plain_text_with_blank():
    markdown = "Intro"

    updated, line_index = ChecklistMarkdown(markdown).append_item()

    assert updated == "Intro\n\n- [ ] New item"
    assert line_index == 2


def test_append_checklist_item_into_empty_text():
    updated, line_index = ChecklistMarkdown("").append_item()

    assert updated == "- [ ] New item"
    assert line_index == 0


def test_checklist_item_text_span_selects_item_label():
    markdown = "Intro\n\n- [ ] New item"

    assert ChecklistMarkdown(markdown).item_text_span(2) == (14, 22)
