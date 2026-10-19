import streamlit as st
import pandas as pd
import re
from PIL import Image
import easyocr
import io

st.set_page_config(page_title="Trævol Log Processing", layout="wide", page_icon="📊")

st.title("📊 Trævol Log Processing")
st.markdown("Ladda upp dina loggbilder för att automatiskt extrahera data och sammanställa till Excel.")

# Initialisera EasyOCR Reader (Danska/Engelska)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['da', 'en'])

reader = load_ocr()

uploaded_files = st.file_uploader(
    "Välj bildfiler (PNG, JPG) eller en befintlig Excel-fil", 
    type=["png", "jpg", "jpeg", "xlsx"], 
    accept_multiple_files=True
)

def process_image(image_bytes, filename):
    image = Image.open(io.BytesIO(image_bytes))
    results = reader.readtext(image_bytes, detail=0)
    text_block = "\n".join(results)
    
    # Regex för att hitta rader i formatet:
    # [Proc] [Dato] [Kunde] [Total tid] [Volume m3] [Mängd/Udtag] [Förbrukning/m3]
    rows = []
    # Matchar mönster som "721209-10-2026 Lager 00:37 0,00 36,64 0,00"
    pattern = re.compile(r'(\d{4,6})\s*(\d{2}-\d{2}-\d{4})\s+([A-Za-z]+)\s+(\d{2}:\d{2})\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)')
    
    for match in pattern.finditer(text_block):
        proc, dato, kunde, tid, vol, mangd, forbrukning = match.groups()
        rows.append({
            "Proc": proc,
            "Dato": dato,
            "Kunde": kunde,
            "Total tid": tid,
            "Volume m³": float(vol.replace(',', '.')),
            "Mängd": float(mangd.replace(',', '.')),
            "Förbrukning/m³": float(forbrukning.replace(',', '.')),
            "Filnamn": filename
        })
    return pd.DataFrame(rows)

if uploaded_files:
    all_dfs = []
    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith('.xlsx'):
            df_ex = pd.read_excel(uploaded_file)
            all_dfs.append(df_ex)
        else:
            with st.spinner(f"Bearbetar {uploaded_file.name}..."):
                df_img = process_image(uploaded_file.getvalue(), uploaded_file.name)
                all_dfs.append(df_img)
                
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        
        st.subheader("Sammanslagen Data")
        st.dataframe(final_df, use_container_width=True)
        
        # Excel-nedladdning
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Trævol Log')
        
        st.download_button(
            label="📥 Ladda ner Sammanställd Excel",
            data=output.getvalue(),
            file_name="travlogg_samlad.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
