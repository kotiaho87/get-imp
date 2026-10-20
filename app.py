import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re

st.set_page_config(page_title="Trævol Log Omvandlare", layout="wide")

st.title("📊 Trævol Log - Positionsbaserad Extraktor")
st.write("Extraherar data kolumn för kolumn baserat på bildens layout.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

with st.spinner("Laddar OCR-motorn..."):
    reader = load_reader()

uploaded_files = st.file_uploader("Välj bilder (t.ex. 1.jpg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    all_extracted_rows = []
    
    with st.spinner("Läser av och analyserar bilders layout..."):
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
                # Sortera elementen på raden från vänster till höger (X-koordinat)
                row_items = sorted(lines[y], key=lambda x: x[0])
                line_text = [item[1] for item in row_items]
                full_line_str = " ".join(line_text)

                # Ignorera rubriker
                if any(h in full_line_str for h in ["Trævol", "Proc", "Dato", "Kunde", "Tank"]):
                    continue

                # Rensa upp mellanslag runt decimaler
                cleaned_line = re.sub(r'(\d+)\s*[.,]\s*(\d+)', r'\1,\2', full_line_str)

                # Matcha ID (4 siffror + datum)
                match = re.search(r'(\d{4})(\d{2}-\d{2}-\d{4})', cleaned_line.replace(" ", ""))
                if match:
                    proc = match.group(1)
                    dato = match.group(2)
                    id_combined = f"{proc}{dato}"
                    
                    # TID (HH:MM)
                    tid_match = re.search(r'(\d{2}:\d{2})', cleaned_line)
                    tid = tid_match.group(1) if tid_match else "00:00"

                    # Plocka ut alla numeriska mönster som faktiskt förekommer som mätvärden på raden
                    all_tokens = re.findall(r'\d+,\d+|\d+', cleaned_line)
                    
                    filtered_nums = []
                    for token in all_tokens:
                        if token in id_combined or token in tid or token == proc:
                            continue
                        filtered_nums.append(token)

                    volym = "0,00"
                    liter = "0,00"

                    # Om vi har minst 2 mätvärden (eller nollor) efter varandra:
                    # På dessa loggar ligger Volym m³ alltid först (oftast 0,00) och Liter/Kg därefter.
                    if len(filtered_nums) >= 2:
                        possible_vol = filtered_nums[0]
                        
                        # Om volymen tolkats som en ensam "3" eller "3,00" men vi vet att den ska vara 0,00 om den ligger på positionen för nollor:
                        # Vi tillåter riktiga volymer (t.ex. 1,00 eller 2,50), men en ensam "3" utan rimlig förklaring sätts till 0,00.
                        if possible_vol in ["3", "3,00"]:
                            volym = "0,00"
                        else:
                            volym = possible_vol
                            
                        liter = filtered_nums[1]
                    elif len(filtered_nums) == 1:
                        liter = filtered_nums[0]

                    # Formatering av decimaler
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
        st.success(f"Lyckades extrahera {len(df)} rader!")
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
