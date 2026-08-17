from io import BytesIO

import pytest

Workbook = pytest.importorskip("openpyxl").Workbook

from core.attachments import extract_document_text


def test_xlsx_attachment_is_extracted_as_real_tabular_text():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Orçamento"
    sheet.append(["Item", "Valor"])
    sheet.append(["Hospedagem", 120])
    payload = BytesIO()
    workbook.save(payload)

    result = extract_document_text(
        payload.getvalue(),
        "orcamento.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert result["success"] is True
    assert result["method"] == "openpyxl"
    assert "PLANILHA: Orçamento" in result["text"]
    assert "Hospedagem | 120" in result["text"]
