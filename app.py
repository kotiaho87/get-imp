import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log Omvandlare", layout="wide")

st.title("📊 Trævol Log Omvandlare")
st.write("Ladda upp dina loggbilder nedan. Datan extraheras och formateras automatiskt direkt!")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

with st.spinner("Laddar OCR-motorn..."):
    reader = load_reader()

uploaded_files = st.file_uploader("Välj bilder (t.ex. 4.jpg, 5.jpg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    all_extracted_rows = []
    
    with st.spinner("Bearbetar bilder och extraherar rader..."):
        for uploaded_file in uploaded_files:
            image = Image.open(uploaded_file)
            image_np = np.array(image)
            
            # Kör OCR
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

                if "Trævol" in full_line_str or "Proc" in full_line_str or "Dato" in full_line_str:
                    continue

                match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', full_line_str.replace(" ", ""))
                if match:
                    proc = match.group(1)
                    dato = match.group(2)
                    
                    tid_match = re.search(r'(\d{2}:\d{2})', full_line_str)
                    tid = tid_match.group(1) if tid_match else "00:00"

                    numbers = re.findall(r'\d+[.,]\d+', full_line_str)

                    mangd = "0,00"
                    forb = "0,00"

                    if len(numbers) >= 2:
                        mangd = numbers[-2].replace('.', ',')
                        forb = numbers[-1].replace('.', ',')
                    elif len(numbers) == 1:
                        mangd = numbers[0].replace('.', ',')

                    all_extracted_rows.append({
                        "Proc": proc,
                        "Dato": dato,
                        "Kunde": "Lager",
                        "Total tid": tid,
                        "Mängd": mangd,
                        "Förbrukning/m³": forb,
                        "Filnamn": uploaded_file.name
                    })

    if all_extracted_rows:
        df = pd.DataFrame(all_extracted_rows)
        st.success(f"Lyckades läsa in {len(df)} rader från bilderna!")
        st.dataframe(df)

        output_file = "travlogg_samlad.xlsx"
        df.to_excel(output_file, index=False)
        
        with open(output_file, "rb") as f:
            st.download_button(
                label="📥 Ladda ner färdig Excel-fil",
                data=f,
                file_name="travlogg_samlad.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("Inga rader kunde hittas. Kontrollera att bilderna är tydliga.")
