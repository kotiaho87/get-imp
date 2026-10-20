import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log Extraktor", layout="wide")

st.title("📊 Trævol Log - Flexibel Extraktor")
st.write("Extraherar ID, TID, VOLYM M3 (stöd för både x,xx och xx,xx) och LITER.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

with st.spinner("Laddar OCR-motorn..."):
    reader = load_reader()

uploaded_files = st.file_uploader("Välj bilder", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    all_extracted_rows = []
    
    with st.spinner("Läser av och analyserar bilder..."):
        for uploaded_file in uploaded_files:
            image = Image.open(uploaded_file)
            image_np = np.array(image)
            
            results = reader.readtext(image_np)
            
            # Gruppera rader baserat på Y-koordinaten
            lines = {}
            for bbox, text, prob in results:
                y_center = (bbox[0][1] + bbox[2][1]) / 2.0
                found_line = False
                for line_y in lines:
                    if abs(line_y - y_center) < 12:
                        lines[line_y].append((bbox[0][0], text.strip()))
                        found_line = True
                        break
                if not found_line:
                    lines[y_center] = [(bbox[0][0], text.strip())]

            sorted_y = sorted(lines.keys())

            for y in sorted_y:
                row_items = sorted(lines[y], key=lambda x: x[0])
                line_text = [item[1] for item in row_items]
                full_line_str = " ".join(line_text)

                # Ignorera rubriker
                if any(h in full_line_str for h in ["Trævol", "Proc", "Dato", "Kunde", "Tank"]):
                    continue

                # Rensa upp mellanslag runt decimaler
                cleaned_line = re.sub(r'(\d+)\s*[.,]\s*(\d+)', r'\1,\2', full_line_str)

                # 1. Hitta ID (4 siffror + datum)
                id_match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', cleaned_line.replace(" ", ""))
                if not id_match:
                    continue
                
                proc = id_match.group(1)
                dato = id_match.group(2)
                id_combined = f"{proc}{dato}"

                # 2. Hitta TID (HH:MM)
                tid_match = re.search(r'(\d{2}[:;.,]\d{2})', cleaned_line)
                if tid_match:
                    tid = tid_match.group(1).replace(';', ':').replace('.', ':').replace(',', ':')
                else:
                    time_fallback = re.search(r'\b(0\d|1\d|2[0-3])([0-5]\d)\b', cleaned_line)
                    tid = f"{time_fallback.group(1)}:{time_fallback.group(2)}" if time_fallback else "00:00"

                # Rensa bort ID och TID för att säkert komma åt mätvärdena
                stripped_line = cleaned_line.replace(proc, "").replace(dato, "")
                if tid_match:
                    stripped_line = stripped_line.replace(tid_match.group(1), "")

                # 3. Hitta alla mätvärden (stöd för både 1-2+ siffror före kommat, t.ex. x,xx eller xx,xx)
                measurements = re.findall(r'\d{1,3}[.,]\d+', stripped_line)

                volym = "0,00"
                liter = "0,00"

                if len(measurements) >= 2:
                    volym = measurements[0].replace('.', ',')
                    liter = measurements[1].replace('.', ',')
                elif len(measurements) == 1:
                    liter = measurements[0].replace('.', ',')

                # Säkerställ korrekt decimalformat
                if "," not in volym:
                    volym = f"{volym},00"
                if "," not in liter:
                    if len(liter) == 4:
                        liter = f"{liter[:2]},{liter[2:]}"
                    else:
                        liter = f"{liter},00"

                all_extracted_rows.append({
                    "ID": id_combined,
                    "TID": tid,
                    "VOLYM M3": volym,
                    "LITER": liter,
                    "Filnamn": uploaded_file.name
                })

    if all_extracted_rows:
        df = pd.DataFrame(all_extracted_rows)
        st.success(f"Lyckades extrahera {len(df)} rader med utökat stöd för volymvärden!")
        st.dataframe(df)

        output_file = "travlogg_renodlad.xlsx"
        df.to_excel(output_file, index=False)
        
        with open(output_file, "rb") as f:
            st.download_button(
                label="📥 Ladda ner färdig Excel-fil",
                data=f,
                file_name="travlogg_renodlad.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("Inga rader kunde hittas. Kontrollera att bilderna är tydliga.")
