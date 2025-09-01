from __future__ import annotations
from typing import Any, Dict, List
from io import BytesIO
import json
import subprocess
import tempfile
import os


def render_chart_to_png(chart_config: Dict[str, Any]) -> bytes:
    """Использует продвинутый generate_chart.py для рендеринга графиков."""
    try:
        # Создаем временный файл для JSON конфига
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(chart_config, f, ensure_ascii=False, indent=2)
            temp_json = f.name
        
        # Запускаем generate_chart.py
        result = subprocess.run(
            ['/home/adminvm/scripts/generate_chart.py'],
            input=json.dumps(chart_config, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=30
        )
        
        # Удаляем временный файл
        os.unlink(temp_json)
        
        if result.returncode == 0:
            # Читаем сгенерированный PNG
            chart_path = result.stdout.strip()
            if os.path.exists(chart_path):
                with open(chart_path, 'rb') as f:
                    return f.read()
            else:
                raise FileNotFoundError(f"Chart file not found: {chart_path}")
        else:
            raise RuntimeError(f"generate_chart.py failed: {result.stderr}")
            
    except Exception as e:
        # Fallback на простой рендеринг если что-то пошло не так
        return _fallback_render(chart_config)


def _fallback_render(chart_config: Dict[str, Any]) -> bytes:
    """Простой fallback рендеринг для случаев ошибок."""
    from io import BytesIO
    import matplotlib.pyplot as plt
    
    ctype = (chart_config or {}).get("type", "bar")
    data = (chart_config or {}).get("data", {})
    labels: List[str] = data.get("labels") or []
    datasets: List[Dict[str, Any]] = data.get("datasets") or []

    fig, ax = plt.subplots(figsize=(9, 5))

    try:
        if ctype == "pie" and datasets:
            values = datasets[0].get("data") or []
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            ax.axis('equal')
        elif ctype == "line" and datasets:
            for ds in datasets:
                ax.plot(labels, ds.get("data") or [], label=ds.get("label") or "", marker='o')
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.4)
        else:  # bar по умолчанию
            width = 0.8 / max(1, len(datasets))
            x = list(range(len(labels)))
            for i, ds in enumerate(datasets):
                vals = ds.get("data") or []
                offset = (i - (len(datasets)-1)/2) * width
                ax.bar([xi + offset for xi in x], vals, width=width, label=ds.get("label") or None)
            if any(ds.get("label") for ds in datasets):
                ax.legend()
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=20, ha='right')

        title = ((chart_config.get("options") or {}).get("plugins") or {}).get("title", {}).get("text")
        if title:
            ax.set_title(title)
    except Exception:
        ax.clear()
        ax.text(0.5, 0.5, "Chart render error", ha='center', va='center')
        ax.axis('off')

    buf = BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    return buf.getvalue()
