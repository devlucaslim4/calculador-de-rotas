from io import BytesIO

import pandas as pd

from ui_helpers import build_template_workbook, validate_upload


def test_template_is_valid_and_contains_an_example_route():
    template = build_template_workbook()
    preview = validate_upload(template)
    assert preview.valid
    assert len(preview.dataframe) == 1


def test_upload_validation_explains_missing_columns():
    output = BytesIO()
    pd.DataFrame({"Origem": ["A"], "Destino": ["B"]}).to_excel(output, index=False)
    preview = validate_upload(output.getvalue())
    assert not preview.valid
    assert "obrigatória" in preview.error


def test_upload_validation_rejects_corrupted_file():
    preview = validate_upload(b"not an excel workbook")
    assert not preview.valid
    assert "corrompido" in preview.error
