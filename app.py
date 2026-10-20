import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
from streamlit_cropper import st_cropper
import numpy as np
import re

st.set_page_config(page_title="Trævol Log - Visuell Extraktor", layout="wide")

st.title("📊 Trævol Log - Visuell Rutframkallare")
st.write("Ladda upp bilden, dra en ruta över tabellen och extrahera värdena direkt till Excel.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

with st.spinner("Laddar OCR-motorn..."):
    reader = load_reader()

uploaded_file = st.file_uploader("Välj en skärmdumpsbild", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    
    st.subheader("1. Markera tabellen i bilden")
    st.write("Dra i hörnen på rutan nedan så att den enbart täcker själva logg-tabellen (exkludera menyer och sidhuvuden).")
    
    # Interaktiv rutframkallare direkt i gränssnittet
    cropped_img = st_cropper(img, realtime_update=True, box_color='#FF4B4B', aspect_ratio=None)
    
    if st.button("🚀 Extrahera data från markerat område"):
        with st.spinner("Läser av den markerade rutan..."):
            image_np = np.array(cropped_img)
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
            all_extracted_rows = []

            for y in sorted_y:
                row_items = sorted(lines[y], key=lambda x: x[0])
                line_text = [item[1] for item in row_items]
                full_line_str = " ".join(line_text)

                # Hitta ID (4 siffror + datum)
                id_match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', full_line_str.replace(" ", ""))
                if not id_match:
                    continue
                
                proc = id_match.group(1)
                dato = id_match.group(2)
                id_combined = f"{proc}{dato}"

                # Hitta TID (HH:MM med kolon)
                tid_match = re.search(r'\b([0-2]\d:[0-5]\d)\b', full_line_str)
                tid = tid_match.group(1) if tid_match else "00:00"

                # Plocka mätvärden
                stripped_line = full_line_str.replace(proc, "").replace(dato, "").replace(tid, "")
                raw_tokens = re.findall(r'\d+[.,]?\d*', stripped_line)
                
                measurements = []
                for token in raw_tokens:
                    clean_t = token.replace('.', '').replace(',', '')
                    if len(clean_t) >= 1:
                        measurements.append(token)

                volym = "0,00"
                liter = "0,00"

                if len(measurements) >= 2:
                    volym = measurements[0]
                    liter = measurements[1]
                elif len(measurements) == 1:
                    liter = measurements[0]

                # Formatering
                volym = volym.replace('.', ',')
                if "," not in volym:
                    volym = f"{volym},00"

                liter = liter.replace('.', ',')
                if "," not in liter:
                    if len(liter) == 4:
                        liter = f"{liter[:2]},{liter[2:]}"
                    else:
                        liter = f"{liter},00"

                all_extracted_rows.append({
                    "ID": id_combined,
                    "TID": tid,
                    "VOLYM M3": volym,
                    "LITER": liter
                })

        if all_extracted_rows:
            df = pd.DataFrame(all_extracted_rows)
            st.success(f"Lyckades extrahera {len(df)} rader från ditt markerade område!")
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
            st.warning("Inga rader kunde hittas i det markerade området. Justera rutan och försök igen.")
