import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from schemaguard.agent import StructuredAgent, StructuredOutputError
from schemaguard.schemas import WeatherReport
from schemaguard.tools import build_weather_tool

load_dotenv(override=True)
st.title("SchemaGuard Agent")

question = st.text_input("Ask about the weather", "What's the weather in Tokyo?")
max_retries = st.sidebar.slider("Max retries", 1, 5, 3)

if st.button("Run agent"):
    agent = StructuredAgent(tools=[build_weather_tool()], max_retries=max_retries)
    with st.spinner("Fetching live weather..."):
        try:
            report = agent.run(question, WeatherReport)
            st.success("Valid output received")
            st.json(report.model_dump())
        except StructuredOutputError as e:
            st.error(str(e))

st.subheader("Validation failure log")
log_file = Path("logs/validation_failures.jsonl")
if log_file.exists():
    lines = log_file.read_text(encoding="utf-8").splitlines()[-20:]
    st.dataframe([json.loads(line) for line in lines])
else:
    st.info("No validation failures logged yet.") 
    
