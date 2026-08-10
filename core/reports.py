import os
import datetime
import csv
import json

def generate_markdown_report(title: str, content: dict, filename: str = "report.md") -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_content = f"# {title}\n\n* **Data de Geração**: {timestamp}\n\n---\n\n"
    for section, text in content.items():
        md_content += f"## {section}\n\n{text}\n\n"
    
    filepath = os.path.join(".", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
    return filepath

def generate_csv_report(data: list, headers: list, filename: str = "report.csv") -> str:
    filepath = os.path.join(".", filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data:
            writer.writerow(row)
    return filepath