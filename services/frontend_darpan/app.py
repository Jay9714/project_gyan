import streamlit as st
import requests

st.set_page_config(layout="wide")
st.title("Darpan (The Mirror) 🔮")
st.header("Project Gyan: Investment Decision System")

st.write("Checking connection to `Setu` API...")

try:
    response = requests.get("http://setu_api:8000/")
    data = response.json()
    st.success(f"Connection OK: {data['status']}")
except Exception as e:
    st.error(f"Connection FAILED to Setu API (http://setu_api:8000). Is it running?")
    st.error(e)