from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd
from io import BytesIO


def build_excel_bytes(table_data: List[Dict[str, Any]], sheet_name: str = "Данные") -> bytes:
    df = pd.DataFrame(table_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
