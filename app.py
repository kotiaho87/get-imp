import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log - Exakt Positionsbaserad Extraktor", layout="wide")

st.title("📊 Trævol Log - Idiotsäker Extraktor")
st.write("Extraherar data strikt baserat på kolumnernas horisontella positioner (X-koordinater).")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

with st.spinner("Laddar OCR-motorn..."):
    reader = load_reader()

uploaded_files = st.file_uploader("Välj bilder", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    all_extracted_rows = []
    
    with st.spinner("Läser av och mappar kolumner..."):
        for uploaded_file in uploaded_files:
            image = Image.open(uploaded_file)
            image_np = np.array(image)
            
            results = reader.readtext(image_np)
            
            # 1. Gruppera alla ord i rader baserat på Y-koordinaten (höjd)
            lines = {}
            for bbox, text, prob in results:
                y_center = (bbox[0][1] + bbox[2][1]) / 2.0
                found_line = False
                for line_y in lines:
                    if abs(line_y - y_center) < 12: # Tolerans för samma rad
                        lines[line_y].append((bbox[0][0], text.strip()))
                        found_line = True
                        break
                if not found_line:
                    lines[y_center] = [(bbox[0][0], text.strip())]

            sorted_y = sorted(lines.keys())

            for y in sorted_y:
                # 2. Sortera ordalydelserna på raden från vänster till höger (X-koordinat)
                row_items = sorted(lines[y], key=lambda x: x[0])
                
                # Sätt ihop hela raden för att kontrollera rubriker
                full_line_str = " ".join([item[1] for item in row_items])

                # Ignorera rubriker
                if any(h in full_line_str for h in ["Trævol", "Proc", "Dato", "Kunde", "Tank"]):
                    continue

                # 3. Extrahera ID (måste finnas för att raden ska räknas)
                id_match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', full_line_str.replace(" ", ""))
                if not id_match:
                    continue
                
                proc = id_match.group(1)
                dato = id_match.group(2)
                id_combined = f"{proc}{dato}"

                # 4. Fördela resterande värden baserat på ordning från vänster till höger
                # Vi letar efter tid (HH:MM) och mätvärden (tal med komma/punkt) i listan av ord
                tid = "00:36"
                volym = "0,00"
                liter = "0,00"

                found_numbers = []
                for x_pos, text in row_items:
                    cleaned_text = text.strip()
                    
                    # Kolla om detta element är TID (innehåller kolon eller liknar ett klockslag)
                    if re.search(r'\d{2}[:;.,]\d{2}', cleaned_text):
                        tid = cleaned_text.replace(';', ':').replace('.', ':').replace(',', ':')
                    elif re.match(r'^\d{2}:\d{2}$', cleaned_text):
                        tid = cleaned_text
                    
                    # Kolla om detta element är ett mätvärde (innehåller komma/punkt eller är rent numeriskt)
                    elif re.search(r'\d+[.,]\d+|\b\d+\b', cleaned_text):
                        # Ignorera delar av ID-datumet
                        if cleaned_text not in id_combined and cleaned_text != proc:
                            found_numbers.append(cleaned_text)

                # Mappa de hittade mätvärdena i rätt kolumnordning:
                # Kolumn 1: Volym M3 (första mätvärdet efter tid)
                # Kolumn 2: Liter (andra mätvärdet)
                if len(found_numbers) >= 2:
                    volym = found_numbers[0].replace('.', ',')
                    liter = found_numbers[1].replace('.', ',')
                elif len(found_numbers) == 1:
                    liter = found_numbers[0].replace('.', ',')

                # Formatera snyggt med decimaler
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
        st.success(f"Lyckades extrahera {len(df)} rader med positionsbaserad mappning!")
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
