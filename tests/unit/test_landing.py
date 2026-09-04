from thai_data_platform.storage.landing import land_file


def test_landing_is_content_addressed_without_overwriting_releases(tmp_path):
    first_source = tmp_path / "first" / "report.xlsx"
    first_source.parent.mkdir()
    first_source.write_bytes(b"release-one")
    second_source = tmp_path / "second" / "report.xlsx"
    second_source.parent.mkdir()
    second_source.write_bytes(b"release-two")

    first = land_file(first_source, "cgd_budget_execution", tmp_path / "raw")
    second = land_file(second_source, "cgd_budget_execution", tmp_path / "raw")

    assert first.path.name == "report.xlsx"
    assert second.path.name.startswith("report.")
    assert first.path.read_bytes() == b"release-one"
    assert second.path.read_bytes() == b"release-two"
