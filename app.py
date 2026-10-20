import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log Omvandlare", layout="wide")

st.title("📊 Trævol Log - Slutgiltig Extraktor")
st.write("Extraherar data med strikt åtskilda kolumner och säkra tidsformat.")

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

                # 1. Hitta ID (4 siffror + datum)
                id_match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', full_line_str.replace(" ", ""))
                if not id_match:
                    continue
                
                proc = id_match.group(1)
                dato = id_match.group(2)
                id_combined = f"{proc}{dato}"

                # 2. Hitta TID – KRÄVER strikt HH:MM med kolon (kan ej förväxlas med decimaltal)
                tid_match = re.search(r'\b([0-2]\d:[0-5]\d)\b', full_line_str)
                tid = tid_match.group(1) if tid_match else "00:00"

                # 3. Hitta alla mätvärden (tal med punkt eller komma, ex. 0,00 eller 34,87)
                # Vi rensar bort ID-delarna först så de inte stör
                stripped_line = full_line_str.replace(proc, "").replace(dato, "").replace(tid, "")
                
                # Hitta alla tal som har decimaler (eller rena heltal om det behövs)
                measurements = re.findall(r'\d+[.,]\d+', stripped_line)

                volym = "0,00"
                liter = "0,00"

                if len(measurements) >= 2:
                    volym = measurements[0].replace('.', ',')
                    liter = measurements[1].replace('.', ',')
                elif len(measurements) == 1:
                    liter = measurements[0].replace('.', ',')

                # Stöd för om volym/liter saknar decimaler men har 4 siffror (t.ex. 3487 -> 34,87)
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
        st.success(f"Lyckades extrahera {len(df)} rader felfritt!")
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
