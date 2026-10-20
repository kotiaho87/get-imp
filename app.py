import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log Omvandlare", layout="wide")

st.title("📊 Trævol Log - Robust Extraktor")
st.write("Extraherar loggar med intelligent korrigering av saknade decimaler.")

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

                # 2. Hitta TID (HH:MM med kolon)
                tid_match = re.search(r'\b([0-2]\d:[0-5]\d)\b', full_line_str)
                tid = tid_match.group(1) if tid_match else "00:00"

                # 3. Hitta alla tal (både med decimaltecken och rena heltal som t.ex. 3252 eller 0)
                stripped_line = full_line_str.replace(proc, "").replace(dato, "").replace(tid, "")
                
                # Fånga både decimaltal och rena heltal/siffersekvenser på raden
                raw_tokens = re.findall(r'\d+[.,]?\d*', stripped_line)
                
                # Filtrera bort oönskade skräptokens
                measurements = []
                for token in raw_tokens:
                    clean_t = token.replace('.', '').replace(',', '')
                    if len(clean_t) >= 1 and clean_t != proc[:2]: # undvik rena ID-delar
                        measurements.append(token)

                volym = "0,00"
                liter = "0,00"

                # Mappa mätvärden
                if len(measurements) >= 2:
                    volym = measurements[0]
                    liter = measurements[1]
                elif len(measurements) == 1:
                    liter = measurements[0]

                # Intelligent formatering av VOLYM M3
                volym = volym.replace('.', ',')
                if "," not in volym:
                    if len(volym) == 1 or volym == "0":
                        volym = f"{volym},00"
                    elif len(volym) == 4: # t.ex. 0000 -> 0,00
                        volym = f"{volym[:1]},{volym[1:]}"

                # Intelligent formatering av LITER (säkrar att saknat komma läggs till)
                liter = liter.replace('.', ',')
                if "," not in liter:
                    if len(liter) == 4: # t.ex. 3487 -> 34,87
                        liter = f"{liter[:2]},{liter[2:]}"
                    elif len(liter) == 5: # t.ex. 13487 -> 134,87
                        liter = f"{liter[:3]},{liter[3:]}"
                    elif len(liter) <= 2:
                        liter = f"{liter},00"
                    else:
                        liter = f"{liter[:2]},{liter[2:]}"

                all_extracted_rows.append({
                    "ID": id_combined,
                    "TID": tid,
                    "VOLYM M3": volym,
                    "LITER": liter,
                    "Filnamn": uploaded_file.name
                })

    if all_extracted_rows:
        df = pd.DataFrame(all_extracted_rows)
        st.success(f"Lyckades extrahera {len(df)} rader med robust decimalhantering!")
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
